#!/usr/bin/env python

import os
import os.path
import sys
import argparse
import getpass
import logging
import logging.handlers
import ConfigParser

import backups.folder
import backups.mysql
import backups.s3
import backups.samba
import backups.smtp
import backups.hipchat

from backups.exceptions import BackupException

def main():
    try:
        # User check
        if getpass.getuser() != 'backups':
            sys.exit("ERROR: Not running as 'backups' user.")

        # Make doubly sure temp files aren't world-viewable
        os.umask(077)

        # Read command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument('configfile', metavar='configfile', nargs=1,
                   help='name of configuration file to use for this run')
        parser.add_argument('-v', dest='verbose', action='store_true')
        args = parser.parse_args()
        configfile = args.configfile[0]
        
        # Read our configuration file
        config = ConfigParser.RawConfigParser()
        config.read(configfile)
        
        # Create an instance, configure and run it
        defaults = config.items('defaults')
        hostname = config.get('defaults', 'hostname')
        
        # Instantiate handlers for any listed destinations
        destinations = []
        for section in config.sections():
            if section == 's3':
                destination = backups.s3.S3(config)
                destinations.append(destination)
            if section == 'samba':
                destination = backups.samba.Samba(config)
                destinations.append(destination)
        if len(destinations) < 1:
            raise BackupException("No destinations listed in configuration file.")
        
        # Instantiate handlers for any listed notifications
        notifications = []
        for section in config.sections():
            if section == 'smtp':
                notification = backups.smtp.SMTP(config)
                notifications.append(notification)
            if section == 'hipchat':
                notification = backups.hipchat.Hipchat(config)
                notifications.append(notification)
        
        # Loop through sections, process those we have sources for
        sources = []
        for section in config.sections():
            if section[0:7] == 'folder-':
                backup_id = section[7:]
                source = backups.folder.Folder(backup_id, config)
                sources.append(source)
            if section[0:6] == 'mysql-':
                backup_id = section[6:]
                source = backups.mysql.MySQL(backup_id, config)
                sources.append(source)
        
        if len(destinations) < 1:
            raise BackupException("No sources listed in configuration file.")
        
        # Loop through the defined sources...
        for source in sources:
            try:
                # Dump and compress
                dumpfile = source.dump_and_compress()
                
                # Send to each listed destination
                for destination in destinations:
                    destination.send(dumpfile, source.name)
                
                # Trigger success notifications as required
                for notification in notifications:
                    notification.notify_success(source.name, source.type, hostname, dumpfile)

            except Exception, e:
                # Trigger notifications as required
                for notification in notifications:
                    notification.notify_failure(source.name, source.type, hostname, e)

            # Done with the dump file now
            if 'dumpfile' in locals() and os.path.isfile(dumpfile):
               os.unlink(dumpfile)
        
        logging.debug("Complete.")

    except KeyboardInterrupt :
        sys.exit()

if __name__ == '__main__':
    main()

