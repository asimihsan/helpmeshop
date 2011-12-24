# ----------------------------------------------------------------------
# Copyright (c) 2011 Asim Ihsan (asim dot ihsan at gmail dot com)
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# File: bristol_board/src/infrastructure/bootstrap.py
#
# Take a fresh Ubuntu install and set it up to support 
# Bristol board.  This will largely be installing source packages,
# setting up files, creating services.
#
# How to use this file:
# - Install Ubuntu 11.04 from scratch on Linode, or start a fresh
#   EC2 AMI on AWS.
# - Change the REMOTE_HOST, REMOTE_USERNAME, REMOTE_PASSWORD
#   variables appropriately.  For EC2 you'll need to use KEY_FILENAME,
#   and this is something you want to use on Linode as well.
# - Run this script.  Will do all the dogwork of installing software
#   and finicky little details about hardening.
#
# - The script will halt at "checkout_code".  This freezes because
#   it doesn't know who github.com is, and this is good because we
#   need to generate a new public key and add it to Github.
# - SSH onto the box, run "ssh-keygen", paste the key into the
#   Github account, then continue the "checkout_code" function.
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
#   Imports.
# ----------------------------------------------------------------------
from __future__ import with_statement
import os
import sys
import logging
import collections
import pprint
from glob import glob

from boto.ec2.connection import EC2Connection
from fabric.api import settings
from fabric.contrib.console import confirm
from fabric.operations import sudo, run, put
from fabric.contrib.files import append, uncomment, sed, exists
from fabric.context_managers import cd, path
import fabric.network
import colorama
from colorama import Fore, Back, Style

# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
#   Logging.
# ----------------------------------------------------------------------
APP_NAME = 'bootstrap'
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
logger = logging.getLogger(APP_NAME)
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
#   Constants to change.
# ----------------------------------------------------------------------
REMOTE_USERNAME = "ubuntu"

# Set either REMOTE_PASSWORD or KEY_FILENAME, where the latter is a patch
# to an authorized RSA keyfile.  KEY_FILENAME is preferred.  Set whatever
# you don't want to use to None.
REMOTE_PASSWORD = "password" 
KEY_FILENAME = None
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
#   Constants to leave alone.
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------

def install_bare_essentials():
    logger = logging.getLogger("%s.install_bare_essentials" % (APP_NAME, ))
    logger.debug("entry.")
    uncomment(filename = r"/etc/apt/sources.list",
              regex = "deb http:\/\/archive.canonical.com\/ubuntu.*partner",
              use_sudo = True)
    uncomment(filename = r"/etc/apt/sources.list",
              regex = "deb-src http:\/\/archive.canonical.com\/ubuntu.*partner",
              use_sudo = True)    
    sudo("apt-get update")
    sudo("yes yes | apt-get upgrade")
    sudo("yes yes | apt-get install git mercurial build-essential unzip python-software-properties ruby curl python-dev htop vim vim-nox")

def setup_timezone():
    logger = logging.getLogger("%s.setup_timezone" % (APP_NAME, ))
    logger.debug("entry.")
    sudo("mv /etc/localtime /etc/localtime.backup")    
    sudo("ln -sf /usr/share/zoneinfo/UTC /etc/localtime")
    sudo("/sbin/hwclock --systohc")

def install_erlang():
    logger = logging.getLogger("%s.install_erlang" % (APP_NAME, ))
    logger.debug("entry.")
    sudo("yes yes | apt-get install curl m4 flex xsltproc fop libncurses5-dev unixodbc-dev openjdk-6-jre openjdk-6-jdk")
    with cd("~"):
        run("rm -rf otp_src_*")    
    with cd("~"):        
        run("wget http://www.erlang.org/download/otp_src_R15B.tar.gz")
        run("tar xvf otp_src_R15B.tar.gz")
    with cd(r"~/otp_src_R15B"):
        run("./configure")
        run("make")
        sudo("make install")
    with cd("~"):
        run("rm -rf otp_src_*")
        
def install_memcached():
    logger = logging.getLogger("%s.install_memcached" % (APP_NAME, ))
    logger.debug("entry.")
    with cd("~"):
        run("rm -rf libevent-2.0.16*")
        run("rm -rf memcached-1.4.10*")
        run("wget https://github.com/downloads/libevent/libevent/libevent-2.0.16-stable.tar.gz")
        run("tar xvf libevent-2.0.16-stable.tar.gz")
        run("wget http://memcached.googlecode.com/files/memcached-1.4.10.tar.gz")
        run("tar xvf memcached-1.4.10.tar.gz")
    with cd(r"~/libevent-2.0.16-stable"):
        run("./configure")
        run("make")
        sudo("make install")
        sudo("ldconfig")
    with cd("~/memcached-1.4.10"):
        run("./configure")
        run("make")
        sudo("make install")
    with cd("~"):
        run("rm -rf libevent-2.0.16*")
        run("rm -rf memcached-1.4.10*")
        
def install_redis():
    logger = logging.getLogger("%s.install_erlang" % (APP_NAME, ))
    logger.debug("entry.")
    with cd("~"):
        run("rm -rf redis-2.4.5*")
        run("wget http://redis.googlecode.com/files/redis-2.4.5.tar.gz")
        run("tar xvf redis-2.4.5.tar.gz")
    with cd("~/redis-2.4.5"):
        run("make")
        sudo("make install")
    with cd("~"):
        run("rm -rf redis-2.4.5*")    
    
def install_postgresql():
    logger = logging.getLogger("%s.install_postgresql" % (APP_NAME, ))
    logger.debug("entry.")
    sudo(r"add-apt-repository ppa:pitti/postgresql")
    sudo("apt-get update")
    sudo("yes yes | apt-get install postgresql-9.0 libpq-dev postgresql-contrib-9.0")    
    sudo("easy_install -U psycopg2")        
    sudo("rm -rf /tmp/tmp*")
    
def init_postgresql():
    logger = logging.getLogger("%s.init_postgresql" % (APP_NAME, ))
    logger.debug("entry")
    sudo("echo -e \"password\\npassword\" | passwd postgres")    
    sudo("rm -f /var/lib/postgresql/.bash_profile")
    sudo("echo export PATH=${PATH}:/usr/lib/postgresql/9.0/bin >> /var/lib/postgresql/.bash_profile", user="postgres")    
    
    sudo("service postgresql stop", user="postgres")            
    sudo("rm -rf /var/lib/postgresql/9.0/main")        
    sudo("initdb -D /var/lib/postgresql/9.0/main", user="postgres")    
    if not exists(r"/var/lib/postgresql/9.0/main/server.crt", use_sudo = True):
        sudo("ln -s /etc/ssl/certs/ssl-cert-snakeoil.pem /var/lib/postgresql/9.0/main/server.crt")
    if not exists(r"/var/lib/postgresql/9.0/main/server.key", use_sudo = True):            
        sudo("ln -s /etc/ssl/private/ssl-cert-snakeoil.key /var/lib/postgresql/9.0/main/server.key")
    sudo("service postgresql start", user="postgres")    
    
    sudo("createuser -s ubuntu", user="postgres")
    sudo("createdb database", user="postgres")    
    run("psql -d database -f /usr/share/postgresql/9.0/contrib/adminpack.sql")
    run("psql -d database -f /usr/share/postgresql/9.0/contrib/hstore.sql")
    run("psql -d database -f /usr/share/postgresql/9.0/contrib/pgcrypto.sql")
    run("psql -d database -f /usr/share/postgresql/9.0/contrib/uuid-ossp.sql")
    run("psql -d template1 -c \"ALTER USER postgres WITH PASSWORD 'password';\"")    
    run("psql -d template1 -c \"ALTER USER ubuntu WITH PASSWORD 'password';\"")    
    
def setup_postgresql():
    logger = logging.getLogger("%s.setup_postgresql" % (APP_NAME, ))
    logger.debug("entry")
    
def setup_python():
    logger = logging.getLogger("%s.setup_python" % (APP_NAME, ))
    logger.debug("entry.")
    with cd("~"):        
        run("curl -O http://python-distribute.org/distribute_setup.py")    
        sudo("python distribute_setup.py")
        run("rm -f distribute*")
    sudo("easy_install -U httplib2 boto fabric colorama twisted pycrypto tornado momoko pycket redis python-memcached paramiko")        
    sudo("rm -rf /tmp/tmp*")
    
def setup_ntp():
    logger = logging.getLogger("%s.setup_ntp" % (APP_NAME, ))
    logger.debug("entry.")
    sudo("yes yes | apt-get install ntp")
    sudo("cp /etc/ntp.conf /etc/ntp.conf.backup")
    sed(filename = "/etc/ntp.conf",
        before = "server.*org",
        after = "",
        use_sudo = True)        
    sed(filename = "/etc/ntp.conf",
        before = "server.*com",
        after = "",
        use_sudo = True)        
    for server_line in ["server 0.uk.pool.ntp.org",
                        "server 1.uk.pool.ntp.org",
                        "server 2.uk.pool.ntp.org",
                        "server 3.uk.pool.ntp.org"]:
        append(filename = "/etc/ntp.conf",
               text = server_line,
               use_sudo = True)
    sudo("service ntp restart")
    
def install_haproxy():
    logger = logging.getLogger("%s.install_haproxy" % (APP_NAME, ))
    logger.debug("entry.")
    with cd("~"):        
        run("wget http://haproxy.1wt.eu/download/1.4/src/haproxy-1.4.18.tar.gz")
        run("tar xvf haproxy-1.4.18.tar.gz")
    with cd(r"~/haproxy-1.4.18"):
        run("make TARGET=linux26")
        sudo("make install")
    with cd("~"):
        run("rm -rf haproxy*")
        
def install_ack():
    logger = logging.getLogger("%s.install_ack" % (APP_NAME, ))
    logger.debug("entry.")    
    sudo("curl -L http://cpanmin.us | perl - --sudo App::cpanminus")
    sudo("cpanm App::Ack")
    
def harden():
    logger = logging.getLogger("%s.harden" % (APP_NAME, ))
    logger.debug("entry.")    
    sed(filename = "/etc/ssh/sshd_config",
        before = "PermitRootLogin yes",
        after = "PermitRootLogin no",
        use_sudo = True)                
    sudo("yes yes | apt-get install ufw")
    sudo("ufw allow ssh")
    sudo("ufw allow 80/tcp")
    sudo("iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080")
    sudo("ufw allow 8080/tcp")
    sudo("ufw allow 443/tcp")
    sudo("iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 8443")
    sudo("ufw allow 8443/tcp")
    sudo("ufw default deny")
    sudo("ufw limit OpenSSH")
    sudo("yes yes | ufw enable")
    sudo("yes yes | apt-get install denyhosts")    
    sudo("cp /etc/denyhosts.conf /etc/denyhosts.conf.backup")
    sed(filename = "/etc/denyhosts.conf",
        before = "AGE_RESET_VALID.*=.*",
        after = "AGE_RESET_VALID=10m",
        use_sudo = True)
        
def checkout_code():
    logger = logging.getLogger("%s.checkout_code" % (APP_NAME, ))
    logger.debug("entry.")    
    with cd("~"):
        run("rm -rf helpmeshop*")
        run("git clone git@github.com:asimihsan/helpmeshop.git")    
        
def setup_bash_profile():
    logger = logging.getLogger("%s.setup_bash_profile" % (APP_NAME, ))
    logger.debug("entry.")    
    sudo("rm -f ~/.bash_profile")
    append(filename = "~/.bash_profile",
           text = "export PATH=${PATH}:/usr/lib/postgresql/9.0/bin:/usr/local/bin")         
           
def setup_ssl():
    """ This isn't 100% unattended.  You'll need to type in 'password' at all
    the prompts.  However, the final SSL certificates will not be password
    protected.
    
    ~/myCA : contains CA certificate, certificates database, generated certificates, keys, and requests
    ~/myCA/signedcerts : contains copies of each signed certificate
    ~/myCA/private : contains the private key 
    """
    logger = logging.getLogger("%s.setup_ssl" % (APP_NAME, ))
    logger.debug("entry.")               
    
    # ------------------------------------------------------------------------
    #   Validate assumptions.
    # ------------------------------------------------------------------------
    assert(os.path.isfile("exampleserver.cnf"))
    assert(os.path.isfile("caconfig.cnf"))    
    # ------------------------------------------------------------------------
    
    sudo("yes yes | apt-get install libssl0.9.8 ca-certificates")
    with cd("~"):
        run("rm -rf ~/myCA")
        run("mkdir -p myCA/signedcerts")
        run("mkdir -p myCA/private")
    for filename in glob("*.cnf"):
        put(filename, os.path.join("/home/ubuntu/myCA/", filename))

    with cd("~/myCA"):
        run("echo '01' > serial")
        run("touch index.txt")        
        
        run("export OPENSSL_CONF=~/myCA/caconfig.cnf; openssl req -x509 -newkey rsa:2048 -out cacert.pem -outform PEM -days 1825")
        run("openssl x509 -in cacert.pem -out cacert.crt")        
        
        run("export OPENSSL_CONF=~/myCA/exampleserver.cnf; openssl req -newkey rsa:2048 -keyout tempkey.pem -keyform PEM -out tempreq.pem -outform PEM")
        run("openssl rsa < tempkey.pem > server_key.pem")
        
        run("export OPENSSL_CONF=~/myCA/caconfig.cnf; openssl ca -in tempreq.pem -out server_crt.pem")
        run("rm -f tempkey.pem && rm -f tempreq.pem")

        run("openssl x509 -in cacert.pem -out cacert.crt")
        run("openssl x509 -in server_crt.pem -out server_crt.crt")
        #run("openssl x509 -in server_key.pem -out server_key.crt")
    
def call_fabric_function(function, remote_host, *args, **kwds):
    if KEY_FILENAME is not None:
        with settings(host_string=remote_host,
                      user=REMOTE_USERNAME,
                      key_filename=KEY_FILENAME):            
            function(*args, **kwds)
    else:
        assert(REMOTE_PASSWORD is not None)
        with settings(host_string=remote_host,
                      user=REMOTE_USERNAME,
                      password=REMOTE_PASSWORD):    
            function(*args, **kwds)        
    
def main():
    logger.info("Starting main.  args: %s" % (sys.argv[1:], ))
    if len(sys.argv) >= 2:
        REMOTE_HOST = sys.argv[1]
    colorama.init()    
    logger.debug("REMOTE_HOST: %s" % (REMOTE_HOST, ))
    
    # ------------------------------------------------------------------
    #   What functions to call.  Uncomment / comment as you wish.
    #   In theory only call these functions once per installation,
    #   but safe, albeit wasteful, to run again.
    # ------------------------------------------------------------------
    functions_to_call = [ \
                         #setup_timezone,
                         #install_bare_essentials,
                         #install_erlang,
                         #install_redis,
                         install_memcached,
                         #install_haproxy,
                         #install_ack,
                         #setup_python,
                         #setup_ntp,
                         #harden,
                         #install_postgresql,
                         #init_postgresql,
                         #setup_postgresql,
                         #checkout_code,
                         #setup_bash_profile,
                         #setup_ssl
                        ]
    # ------------------------------------------------------------------
    logger.info("executing the following functions:\n%s" % (pprint.pformat(functions_to_call), ))
    try:        
        for function_to_call in functions_to_call:
            call_fabric_function(function_to_call,
                                 remote_host = REMOTE_HOST)        
    finally:
        logger.info("Cleanup.")
        logger.debug("Disconnect all SSH sessions...")
        fabric.network.disconnect_all()
    
if __name__ == "__main__":
    main()


