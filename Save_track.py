import websocket
import json
import os
import time
from datetime import datetime, timezone
import requests
import sys
import signal

#this program listens to signal k for positions and saves them locally. 
#the program starts and stops the tracking automatically.
#Sends a notification to the user when boat is inactive. 
# The user can choose to stop the tracking manually by clicking yes, og restart the timer by clicking no. 
#If the user does not respond within a certain time, the tracking will be stopped automatically.

#if windows change folder to one with write permissions, if linux (raspberry pi) use the home folder.
if sys.platform.startswith("win"):
    ACTIVE_DIR = r"C:\signalk\signalkhome\.signalk\boatlog_active"
else:
    # Raspberry Pi (Linux) 
    ACTIVE_DIR = os.path.expanduser("~/.signalk/boatlog_active")

SignalK_url = "http://localhost:3000/signalk/v2/api/resources"


def load_config():
    config_file = 'config.json'
    if not os.path.exists(config_file):
        print(f"error - config file '{config_file}' not found. Please create it with the necessary settings.")
        sys.exit(1)
    with open(config_file, 'r') as f:
        return json.load(f)
    

# Hent config og tildel værdier
config = load_config()

# Globale variabler sat fra config
ACTIVE_DIR = config.get('active_dir', os.path.expanduser("~/.signalk/boatlog_active"))
SignalK_url = config.get('signalk_url', "http://localhost:3000") + "/signalk/v2/api/resources"

# Thresholds og timing fra config med fallback-værdier
speed_start_threshold = config.get('speed_start_threshold', 0.5)
speed_stop_threshold = config.get('speed_stop_threshold', 0.2)
log_interval = config.get('log_interval', 5)
autostop_delay_notification = config.get('autostop_delay_notification', 600)
auto_stop_delay = config.get('auto_stop_delay', 300)
min_points_to_save = config.get('min_points_to_save', 1)


class BoatlogRecorder:
    def __init__(self):
        self.state = "IDLE" #IDLE, RECORDING, WAITING_FOR_STOP
        self.points = []
        self.current_trip_name = None
        self.last_save_time = 0
        self.last_movement_time = time.time()

        #creates the folder not created
        os.makedirs(ACTIVE_DIR, exist_ok=True)

    #sends a notfication to the user via signalk, when the boat seems to be inactive.
    def send_notification(self, message, state="normal"):        
            base_url = config.get('signalk_url', "http://localhost:3000")
            url = f"{base_url}/signalk/v1/api/vessels/self/notifications/navigation/logbook"
            try:
                payload = {"value": {"message": message, "state": state, "method": ["visual", "sound"]}}
            
                response = requests.put(url, json=payload, timeout=2)
                
                if response.status_code == 200:
                    print(f"[*] SUCCES: Notifikation sendt!")
                else:
                    print(f"[!] Fejl {response.status_code}: {response.text}")
            except Exception as err:
                print(f"[!] Netværksfejl: {err}")

    #method to start create the fil for the track.
    def start_new_trip(self):
        self.state = "RECORDING"
        self.current_trip_id = datetime.now().strftime("%d.%m.%Y %H.%M")
        self.points = []
        self.send_notification(f"NEW TRACK STARTED: {self.current_trip_id}", "normal")

        #for testing:
        print(f"[*] TRACKING STARTED: {self.current_trip_id}")


    #method to start the actual recording of the track, by saving the points to a file.
    def record_point(self, lat, lon, sog, sk_time=None):
        #ignore non valid positions
        if lat == 0 or lon == 0: return
        timestamp = sk_time if sk_time else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


        now = time.time()
        #if the boat is moving above threshold, start recording or resume recording if waiting for stop
        if sog > speed_start_threshold:
            self.last_movement_time = now
            if self.state == "IDLE":
                self.start_new_trip()
            elif self.state == "WAITING_FOR_STOP":
                self.state = "RECORDING"
                self.send_notification("TRACK RESUMED", "normal")

        if self.state != "IDLE":
            if now - self.last_save_time >= log_interval:
                

                point ={
                    "lat": round(lat, 5),
                    "lon": round(lon, 5),
                    "t": timestamp
                }
                self.last_save_time = now

                #save to ssd
                active_file = os.path.join(ACTIVE_DIR, f"{self.current_trip_id}.json")
                with open(active_file, "a") as f:
                    f.write(json.dumps(point) + "\n")
            
        time_since_move = now - self.last_movement_time

        if self.state == "RECORDING" and time_since_move > autostop_delay_notification:
            self.state = "WAITING_FOR_STOP"
            self.send_notification("NO MOVEMENT DETECTED. TRACK WILL AUTOMATICALLY STOP IN 5 MINUTES", "warning")

        if self.state == "WAITING_FOR_STOP" and time_since_move > (auto_stop_delay + autostop_delay_notification):
            self.finalize_trip()

    def finalize_trip(self):
        if not self.current_trip_id:
            return
        
        active_path = os.path.join(ACTIVE_DIR, f"{self.current_trip_id}.json")
        final_filename = f"{self.current_trip_id}.json"
        
        

        self.points = []
        if os.path.exists(active_path):
            with open(active_path, "r") as f:
                for line in f:
                    if line.strip():
                        self.points.append(json.loads(line))
        

        #don't save, if there are not enough points, to avoid saving false tracks.
        if len(self.points) < min_points_to_save:
            print(f"[-] TRACK ABORTED: Not enough points ({len(self.points)} < {min_points_to_save})")
            self.send_notification(f"TRACK ABORTED: Not enough points ({len(self.points)} < {min_points_to_save})")
            active_path = os.path.join(ACTIVE_DIR, f"{self.current_trip_id}.json")
            if os.path.exists(active_path): os.remove(active_path)
        else:
            final_filename = f"{self.current_trip_id}.json"


            geojson = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[p['lon'], p['lat']] for p in self.points]
                },
                "properties": {
                    "name": self.current_trip_id,
                    "startTime": self.points[0]['t'],
                    "endTime": self.points[-1]['t'],
                    "point_count": len(self.points),
                    "times": [p['t'] for p in self.points]
                }
            }
            #posts the final track to signalk, tracks-pending.
            track_url = f"{SignalK_url}/tracks-pending/{self.current_trip_id}"
            try:
                response = requests.put(track_url, json=geojson, timeout=5)
                if response.status_code in [200, 201]:
                    print(f"[*] TRACK SAVED: {self.current_trip_id} with {len(self.points)} points")
                    self.send_notification(f"TRACK SAVED: {self.current_trip_id}", "normal")
                    if os.path.exists(active_path): os.remove(active_path)
                else:
                    print(f"[!] FEJL VED GEMNING AF TRACK: {response.status_code} - {response.text}")
                    self.send_notification(f"ERROR SAVING TRACK: {response.status_code}", "error")
            except Exception as err:
                print(f"[!] NETVÆRKSFEJL VED GEMNING AF TRACK: {err}")
                self.send_notification(f"NETWORK ERROR SAVING TRACK: {err}", "error")
            
        self.state = "IDLE"
        self.points = []

recorder = BoatlogRecorder()

def handle_exit(sig, frame):
    recorder.finalize_trip()
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)
    

#Filters signalk messages for the relevant data and sends it to the recorder.
def on_message(ws, message):
    data = json.loads(message)
    # Vi graver kun i 'updates' hvis det findes
    if 'updates' in data:
        lat, lon, sog, sk_time = None, None, 0, None
        for update in data['updates']:
            if 'values' in update:
                for val in update['values']:
                    if val['path'] == 'navigation.position':
                        lat = val['value']['latitude']
                        lon = val['value']['longitude']
                    if val['path'] == 'navigation.speedOverGround':
                        sog = val['value'] * 1.94384
                    if val['path'] == 'navigation.datetime':
                        sk_time = val['value']
                        print(f"[*] MODTAGET GPS TID: {sk_time}")
        
        if lat is not None and lon is not None:
            recorder.record_point(lat, lon, sog, sk_time)

def on_open(ws):
    print("[!] Forbindelse til Signal K etableret!")

def on_error(ws, error):
    print(f"[!] FEJL: {error}")

def on_close(ws, close_status_code=None, close_msg=None):
    print("### Forbindelse afbrudt - afslutter turen... ###")
    recorder.finalize_trip()
    

ws_url = "ws://localhost:3000/signalk/v1/stream?subscribe=all" 


while True:
    print("[*] Forsøger at forbinde til Signal K...")
    ws = websocket.WebSocketApp(
        ws_url, 
        on_message=on_message, 
        on_open=on_open, 
        on_error=on_error,
        on_close=on_close
    )
    # run_forever vil køre indtil forbindelsen brydes
    ws.run_forever()
    
    # Vent 5 sekunder før vi prøver at genforbinde
    print("[!] Forbindelse tabt. Prøver igen om 5 sekunder...")
    time.sleep(5)


        



    



