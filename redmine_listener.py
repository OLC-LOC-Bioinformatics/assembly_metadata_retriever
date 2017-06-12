from pyaccessories.TimeLog import Timer
import os
from RedmineAPI.RedmineAPI import RedmineInterface
from pyaccessories.SaveLoad import SaveLoad
import base64
# TODO documentation


class Run(object):
    def main(self, force):
        if self.first_run == 'yes':
            choice = 'y'
            if force:
                raise ValueError('Need redmine API key!')
        else:
            if force:
                choice = 'n'
            else:
                self.t.time_print("Would you like to set the redmine api key? (y/n)")
                choice = input()
        if choice == 'y':
            self.t.time_print("Enter your redmine api key (will be encrypted to file)")
            self.redmine_api_key = input()
            # Encode and send to json file
            self.loader.redmine_api_key_encrypted = self.encode(self.key, self.redmine_api_key).decode('utf-8')
            self.loader.first_run = 'no'
            self.loader.dump(self.config_json)
        else:
            # Import and decode from file
            self.redmine_api_key = self.decode(self.key, self.redmine_api_key)

        import re
        if not re.match(r'^[a-z0-9]{40}$', self.redmine_api_key):
            self.t.time_print("Invalid Redmine API key!")
            exit(1)

        self.redmine = RedmineInterface('http://redmine.biodiversity.agr.gc.ca/', self.redmine_api_key)

        self.main_loop()

    def completed_response(self, redmine_id, missing):
        notes = "Completed extracting files. Results stored at %s" % os.path.join("NAS/bio_requests/%s" % redmine_id)
        if len(missing) > 0:
            notes += '\nMissing some files:\n'
            for file in missing:
                notes += file + '\n'

        # Assign it back to the author
        get = self.redmine.get_issue_data(redmine_id)

        self.redmine.update_issue(redmine_id, notes, status_change=4, assign_to_id=get['issue']['author']['id'])

    def main_loop(self):
        import time
        while True:
            self.make_call()
            self.t.time_print("Waiting for next check.")
            time.sleep(self.seconds_between_redmine_checks)

    def make_call(self):
        self.t.time_print("Checking for metadata requests...")

        data = self.redmine.get_new_issues('cfia')

        found = []
        import re
        prog = re.compile(r'^assembly&metadata-\d{2}(\d{2}-\d{1,2}-\d{1,2})$')
        for issue in data['issues']:
            if issue['status']['name'] == 'New':
                # Get rid of caps and spaces and match
                subj = ''.join(issue['subject'].lower().split())
                result = re.fullmatch(prog, subj)
                if result:
                    found.append({
                        'id': issue['id'],
                        'folder': ''.join(result.group(1).split('-'))
                    })

        self.t.time_print("Found %d issues..." % len(found))

        while len(found) > 0:  # While there are still issues to respond to
            self.respond_to_issue(found.pop(len(found)-1))

        # Check on old jobs
        self.t.time_print("Checking on old issues: ")
        for job in self.queue:
            msg = str(job['id']) + ': '
            if self.check_assembly(job['folder']):
                'Uploading.'
                results_zip = self.retrieve_files(job)

                response = "Retrieved data. Also stored at %s." % results_zip
                self.redmine.upload_file(results_zip, job['id'], 'application/zip', status_change=4,
                                         additional_notes=response + self.bottext)
                self.queue.remove(job)
            else:
                msg += 'Not ready.'
            self.t.time_print(msg)

    def respond_to_issue(self, job):
        # Run extraction
        if self.redmine.get_issue_data(job['id'])['issue']['status']['name'] == 'New':
            self.t.time_print("Found metadata retrieving job to run. ID: %s, folder %s" % (str(job['id']),
                                                                                           str(job['folder'])))

            if self.check_assembly(job['folder']):
                self.t.time_print('Uploading files...')
                # Retrieve
                results_zip = self.retrieve_files(job)

                response = "Retrieved data. Also stored at %s." % results_zip
                self.redmine.upload_file(results_zip, job['id'], 'application/zip', status_change=4,
                                         additional_notes=response + self.bottext)
            else:
                # response
                response = "Waiting for assembly to complete..."
                self.t.time_print(response)
                self.t.time_print("Adding to queue")
                self.queue.append(job)
                self.queue_loader.queue = self.queue
                self.queue_loader.dump()

                # Set the issue to in progress
                self.redmine.update_issue(job['id'], notes=response + self.bottext, status_change=2)

    def check_assembly(self, datestr):
        directory = os.path.join(self.nas_mnt, 'WGSspades', datestr + '_Assembled')
        return bool(os.path.isdir(directory))

    def retrieve_files(self, job):
        results_folder = os.path.join(self.nas_mnt, 'bio_requests', str(job['id']))
        os.makedirs(results_folder)
        results_zip = os.path.join(results_folder, str(job['id']) + '.zip')
        directory = os.path.join(self.nas_mnt, 'WGSspades', job['folder'] + '_Assembled')
        self.zip_results(os.path.join(directory, 'reports'), results_zip)
        return results_zip

    def zip_results(self, r_folder, outfolder):
        import zipfile
        # Zip all the files
        self.t.time_print("Creating zip file %s" % outfolder)

        try:
            os.remove(outfolder)
        except OSError:
            pass

        zipf = zipfile.ZipFile(outfolder, 'w', zipfile.ZIP_DEFLATED)
        for file in os.listdir(r_folder):
            zipf.write(os.path.join(r_folder, file))
            self.t.time_print("Zipped %s" % file)

        zipf.close()

    @staticmethod
    def encode(key, string):
        encoded_chars = []
        for i in range(len(string)):
            key_c = key[i % len(key)]
            encoded_c = chr(ord(string[i]) + ord(key_c) % 256)
            encoded_chars.append(encoded_c)
        encoded_string = "".join(encoded_chars)
        encoded_string = bytes(encoded_string, "utf-8")

        return base64.urlsafe_b64encode(encoded_string)

    @staticmethod
    def decode(key, string):
        decoded_chars = []
        string = base64.urlsafe_b64decode(string).decode('utf-8')
        for i in range(len(string)):
            key_c = key[i % len(key)]
            encoded_c = chr(abs(ord(str(string[i]))
                                - ord(key_c) % 256))
            decoded_chars.append(encoded_c)
        decoded_string = "".join(decoded_chars)

        return decoded_string

    def __init__(self, force):
        # import logging
        # logging.basicConfig(level=logging.INFO)
        # Vars
        import sys
        self.script_dir = sys.path[0]
        self.config_json = os.path.join(self.script_dir, "config.json")

        # Set up timer/logger
        import datetime
        if not os.path.exists(os.path.join(self.script_dir, 'runner_logs')):
            os.makedirs(os.path.join(self.script_dir, 'runner_logs'))
        self.t = Timer(log_file=os.path.join(self.script_dir, 'runner_logs',
                                             datetime.datetime.now().strftime("%d-%m-%Y_%S:%M:%H")))
        self.t.set_colour(30)

        # Save issues found to a queue (load existing issues if bot needs to restart)
        self.queue_loader = SaveLoad(os.path.join(self.script_dir, 'queue.json'), create=True)
        self.queue = self.queue_loader.get('queue', default=[], ask=False)

        # Get encrypted api key from config
        # Load the config
        self.loader = SaveLoad(self.config_json, create=True)
        self.redmine_api_key = self.loader.get('redmine_api_key_encrypted', default='none', ask=False)

        # If it's the first run then this will be yes
        self.first_run = self.loader.get('first_run', default='yes', ask=False)

        self.nas_mnt = os.path.normpath(self.loader.get('nasmnt', default="/mnt/nas/", get_type=str))
        self.seconds_between_redmine_checks = self.loader.get('secs_between_redmine_checks', default=600, get_type=int)
        self.key = 'Sixteen byte key'

        self.redmine = None

        self.bottext = '\n\n_I am a bot. This action was performed automatically._'

        try:
            self.main(force)
        except Exception as e:
            import traceback
            self.t.time_print("[Error] Dumping...\n%s" % traceback.format_exc())
            raise

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--force", action="store_true",
                        help="Don't ask to update redmine api key")

    args = parser.parse_args()
    Run(args.force)
