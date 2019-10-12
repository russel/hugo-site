#!/usr/bin/python3
#
# Library code for ACCU website. Validate user against Xaraya website database.
#

import argparse
import hashlib
import sys

import pymysql

class Checker:
    def __init__(self, dbhost, dbpass):
        self.db = pymysql.connect(host=dbhost,
                                  user='accuorg_xarad',
                                  password=dbpass,
                                  db='accuorg_xar',
                                  charset='latin1')

    def __getuser(self, username, userpass):
        cursor = self.db.cursor()
        try:
            cursor.execute('SELECT xar_pass, xar_name, xar_status FROM xar_roles LEFT JOIN xar_subscriptions USING (xar_uid) WHERE xar_uname=%s', username)
            row = cursor.fetchone()
            m = hashlib.md5()
            m.update(userpass.encode('latin1'))
            if m.hexdigest() != row[0]:
                return ()
            return (row[1], row[2])
        except:
            return ()

    def user(self, username, userpass):
        user_info = self.__getuser(username, userpass)
        return bool(user_info)

    def member(self, username, userpass):
        user_info = self.__getuser(username, userpass)
        return bool(user_info) and user_info[1] == 1

def main():
    parser = argparse.ArgumentParser(description='test password library')
    parser.add_argument('--dbhost', dest='dbhost',
                        action='store', default='localhost',
                        help='database host', metavar='HOSTNAME')
    parser.add_argument('--dbpass', dest='dbpass',
                        action='store', required=True,
                        help='database password', metavar='PASSWORD')
    parser.add_argument('-u', '--user', dest='user',
                        action='store', required=True,
                        help='username', metavar='USERNAME')
    parser.add_argument('-p', '--password', dest='passwd',
                        action='store', required=True,
                        help='user password', metavar='PASSWORD')
    args = parser.parse_args()

    checker = Checker(args.dbhost, args.dbpass)
    if checker.member(args.user, args.passwd):
        print('User \'{name}\' is ACCU member.'.format(name=args.user))
    elif checker.user(args.user, args.passwd):
        print('Name \'{name}\' is ACCU website user.'.format(name=args.user))
    else:
        print('Unknown user or wrong password')
    sys.exit(0)

if __name__ == "__main__":
    main()

# Local Variables:
# mode: Python
# End:
