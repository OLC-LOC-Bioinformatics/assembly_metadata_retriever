# assembly_metadata_retriever
Written by Devon Mack, June 2017                                             

This program will upload any requested assemblies and metadata to redmine

## Prerequisites:
- Python 3
      
## Installation
Run the command:
```console
git clone https://github.com/devonpmack/assembly_metadata_retriever.git --recursive
```
### Configuration of the redmine listener:     
Run the program and it will ask you for all the configuration it needs.
```console
python3 redmine_listener.py
```
It will now ask you for all the configuration options/requirements:
- nasmnt: path to the NAS
- seconds_between_redmine_checks: How many seconds to wait between checks on redmine looking for new SNVPhyls to run

Finally enter your Redmine API Key, you can find your API key on your account page ( /my/account ) when logged in, on the right-hand pane of the default layout.

#### To run the server:
```console
python3 redmine_listener.py
```

### Running the Redmine Listener permanently
First install the supervisor package
```console
sudo apt-get install supervisor
```
Create a config file for your daemon at /etc/supervisor/conf.d/assembly_retriever.conf
```
[program:assembly_retriever]
directory=/path/to/project/root
command=python3 redmine_listener.py -f
autostart=true
autorestart=true
```
Replace /path/to/project/root with the path to the folder you cloned auto_snvphyl into.

Restart supervisor to load your new .conf
```
supervisorctl update
supervisorctl restart assembly_retriever
```