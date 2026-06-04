This program uses Signal K to log gps locations and times. This data is first saved locally, then uploaded to ressources plugin in Signal K. I have called the ressources paths the following: tracks-pending and uploaded-tracks to hopefully not intervene with other programs.
locally i called the folder: boatlog-active
the idea is to save in one folder during sailing, then move it to a folder where multiple tracks can be uploaded once internet is possible. Then when uploaded move it to uploaded tracks to not make duplicates.
Starts logging when SOG threshold is surpassed, and ends the trip when there hasn't been any movement for a while. 
From there it can be uploaded. I have made a file for this, or you can make your own. 
I have however only tried the system as a full system, and on windows. So beware that it might be more dependent than intended.

Remember to change the config file for your paths and thresholds.

## Installation
1. Clone this repository to your boat's computer:
   `git clone https://github.com/YOUR_USERNAME/boatlog.git`
2. Navigate to the folder: `cd boatlog`
3. Run the installation script:
   `sudo ./install.sh`


## Configuration
Before running, edit the `config.json` file to match your setup:
- `signalk_url`: The URL of your local Signal K server.
- `active_dir`: Path where temporary tracking data is stored.

## Other relevant repositories
https://github.com/BirkJefta/GPXUpload



