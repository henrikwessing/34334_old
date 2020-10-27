import errno
import os
import re
import sys
import pwd
import time
import json


#docker handling code
import lab

import argparse
import netifaces
import traceback
import subprocess

from multiprocessing import Process

parser = argparse.ArgumentParser(description='Wireshark for Security Professionals Lab')
parser.add_argument('--debug', action='store_true', default=False)
args = parser.parse_args()

NSROOT = lab.ns_root

# import the Flask class from the flask module, try to install if we don't have it
try:
    from flask import Flask, render_template, request, jsonify
except:
    try:
        subprocess.check_call(['pip3', 'install', 'flask'])
        from flask import Flask, render_template, request, jsonify

    except:
        subprocess.check_call(['apt-get', 'install', 'python3-flask'])
        from flask import Flask, render_template, request, jsonify



# create the application object
app = Flask(__name__)
app.config.from_object(__name__)


def get_connections():
    """this should return all of the machines that are connected"""

    tmp = []

    for ns in lab.ns_root.ns:
        for nic in ns.nics:
            if 'root' in nic:
                yield 1,ns.pid
            for os in lab.ns_root.ns:
                if os != ns and nic in os.nics and nic not in tmp:
                    tmp.append(nic)
                    print('%s connected %s' % (ns.pid,os.pid))
                    yield ns.pid,os.pid



def psef(grep):
    """this is python replacement for ps -ef, based off of
        http://stackoverflow.com/questions/2703640/process-list-on-linux-via-python"""

    pids = [pid for pid in os.listdir('/proc') if pid.isdigit()]

    for pid in pids:
        try:

            #read the command line from /proc/<pid>/cmdline
            with open(os.path.join('/proc', pid, 'cmdline'), 'rb') as cmd:
                cmd = cmd.read()
                if grep in cmd:
                    return pid, cmd

        #if the proc terminates before we read it
        except IOError:
            continue

    return False




# use decorators to link the function to a url
@app.route('/')
def launcher():

    dockers = []

    for docker in NSROOT.ns:
        dockers.append(docker)

    return render_template('launcher2.html', dockers=dockers)


@app.route('/getnet')
def getnet():

    """This returns the nodes and edges used by visjs, node = { 'id': ns.pid, 'label': ns.name, 'title': ip_address }
        edges = { 'from': ns_connected_from, 'to': ns_connected_to }"""
    print("NU ER VI I GETNET")
    data = {}
    data['nodes'] = []
    data['edges'] = []

    for ns in lab.ns_root.ns:
        tmp = {}
        tmp['id'] = ns.pid
        tmp['label'] = ns.name

        if ns.name == 'inet':
            tmp['color'] = 'rgb(0,255,0)'

        tmp_popup = ''
        for ips in ns.get_ips():
            # { 'nic' : ip }
            tmp_popup += '%s : %s <br>' % ips.popitem()

        tmp['title'] = tmp_popup
        data['nodes'].append(tmp)

    tmp_popup = ''
    #now add the root ns
    for ips in lab.ns_root.get_ips():
        tmp_popup += '%s : %s <br>' % ips.popitem()

    data['nodes'].append({'id' : 1, 'label' : 'kali', 'color' : 'rgb(204,0,0)', 'title' : tmp_popup})

    for f,t in get_connections():
        tmp = {}
        tmp['from'] = f
        tmp['to'] = t
        data['edges'].append(tmp)

    print(data)
    return jsonify(**data)



@app.route('/runshark', methods=['POST', 'GET'])
def runshark():
   """this runs wireshark within the network namespace"""
   error = None
   if request.method == 'POST':
       print('[*] POST IN RUNSHARK')
       for key in request.form.keys():
           if request.form[key] == '1':
               lab.runshark('root')
           for ns in NSROOT.ns:
               if ns.pid == request.form[key]:
                   print(ns.pid)
                   print(ns.name)
                   lab.runshark(ns.name)
   return 'launched'


@app.route('/setupfirewall')
def setupfw():
    """start the firewall network"""

    if len(NSROOT.ns) >= 1:
        return 'REFRESH'

    try:
        lab.setup_network_firewall('eth0')
        time.sleep(3)
        return 'REFRESH'

    except:
        print(traceback.format_exc())
        return 'ERROR'

@app.route('/setuprouting')
def setuprouting():
    """start the routing network"""

    if len(NSROOT.ns) >= 1:
        return 'REFRESH'

    try:
        lab.setup_network_routing('eth0')
        time.sleep(3)
        return 'REFRESH'

    except:
        print(traceback.format_exc())
        return 'ERROR'





@app.route('/shutdown')
def shutdown():
    """cleans up mess"""

    lab.ns_root.shutdown()
    time.sleep(3)
    return ''


# start the server with the 'run()' method
if __name__ == '__main__':


    script_dir = os.path.dirname(os.path.realpath(__file__))
    cwd = os.getcwd()

    if script_dir != cwd:
        print('[*] Not run from the script directory, changing dirs')
        #move to the directory the script is stored in
        os.chdir(script_dir)

    #check to see if the w4sp-lab user exists
    try:
        temppwd = pwd.getpwnam('cybertek')
        print("Password entry: "  + str(temppwd))
    except KeyError:
        print('[*] w4sp-lab user non-existant, creating')
        try:
            lab.utils.r('useradd -m cybertek -s /bin/bash -G sudo,wireshark -U')
        except:
            lab.utils.r('useradd -m cybertek -s /bin/bash -G sudo -U')  
        print("[*] Please run: 'passwd cybertek' to set your password, then login as w4sp-lab and rerun lab")
        sys.exit(-1)

    #check to see if we logged in as w4sp-lab
    if os.getlogin() != 'cybertek':
        print('[*] Please login as cybertek and run script with sudo')
        sys.exit(-1)


    #check dumpcap
    lab.check_dumpcap()


    #see if we can run docker
    try:
        images = subprocess.check_output([b'docker', b'images']).split(b'\n')
    except (OSError,subprocess.CalledProcessError) as e:

        #if e is of type subprocess.CalledProcessError, assume docker is installed but service isn't started
        if type(e) == subprocess.CalledProcessError:
            subprocess.call(['service', 'docker', 'start'])
            images = subprocess.check_output([b'docker', b'images']).split(b'\n')

        elif e.errno == errno.ENOENT:
            # handle file not found error, lets install docker
            subprocess.call(['apt-get', 'update'])
            subprocess.call(['apt-get', 'install', '-y',
                            'bridge-utils',
                            'apt-transport-https', 'ca-certificates',
                            'software-properties-common'])

            # check if we already configured docker repos
            with open('/etc/apt/sources.list', 'a+') as f:
                if 'docker' not in f.read():

                    #adding the docker gpg key and repo
                    subprocess.call(['wget', 'https://yum.dockerproject.org/gpg',
                                    '-O', 'docker.gpg'])

                    subprocess.call(['apt-key', 'add', 'docker.gpg'])

                    #add the stretch repo, need to figure out how to map kali versions
                    #to debian versions

                    #f.write('\ndeb https://apt.dockerproject.org/repo/ debian-stretch main\n')

            subprocess.call(['apt-get', 'update'])
            subprocess.call(['apt-get', '-y', 'install', 'docker.io'])
            subprocess.call(['service', 'docker', 'start'])
            images = subprocess.check_output([b'docker', b'images']).split(b'\n')

        else:
            # Something else went wrong
            raise



    try:
        tmp_n = 0
        for image in images:
            if b'34334' in image:
                tmp_n += 1
        #Check that all needed images have been created
        if tmp_n > len(os.listdir('images')):
            print('[*] 34334 images available')

        else:
            print('[*] Not enough 34334 images found, building now')
            lab.docker_build('images/')

    except:
        #just a placeholder
        raise

    #adding logic to handle writing daemon.json so we can disable docker iptables rules
    daemon_f = '/etc/docker/daemon.json'
    if not os.path.isfile(daemon_f):
        with open(daemon_f, 'w+') as f:
            f.write('{ "iptables": true }')

    subprocess.call(['iptables', '-P', 'INPUT', 'ACCEPT'])
    subprocess.call(['iptables', '-P', 'FORWARD', 'ACCEPT'])
    subprocess.call(['iptables', '-P', 'OUTPUT', 'ACCEPT'])
    subprocess.call(['iptables', '-t', 'nat', '-F'])
    subprocess.call(['iptables', '-t', 'mangle', '-F'])
    subprocess.call(['iptables', '-F'])
    subprocess.call(['iptables', '-X'])


    lab.docker_clean()


    app.config['DEBUG'] = args.debug
    p = Process(target=app.run)
    p.start()

    time.sleep(3)

    print('[*] Lab Launched, Start browser at http://127.0.0.1:5000')
    print('[*] Do not close this terminal. Closing Terminal will terminate lab.')
  

