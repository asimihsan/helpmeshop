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
import platform

from boto.ec2.connection import EC2Connection
from fabric.api import settings
from fabric.contrib.console import confirm
from fabric.operations import sudo, run, put
from fabric.contrib.files import contains, append, uncomment, comment, sed, exists
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
REMOTE_IP_ADDRESS = "178.79.168.49"
REMOTE_SSH_PORT = 22
REMOTE_HOSTNAME = "katara"
REMOTE_USERNAME = "ubuntu"

# Set either REMOTE_PASSWORD or KEY_FILENAME, where the latter is a path
# to an authorized RSA keyfile.  KEY_FILENAME is preferred.  Set whatever
# you don't want to use to None.
REMOTE_PASSWORD = "kleafEgcasp6"
#REMOTE_PASSWORD = "password"

if platform.system() == "Windows":
    KEY_FILENAME = r"C:\Users\ai\Documents\puttykey-4096.pub"
    OPENSSH_AUTHORIZED_KEY_FILE = r"C:\Users\ai\Documents\puttykey-4096-openssh.pub"
else:
    KEY_FILENAME = "/Users/asim/.ssh/id_rsa.pub"
    OPENSSH_AUTHORIZED_KEY_FILE = "/Users/asim/.ssh/id_rsa.pub"

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
    sudo("yes yes | apt-get install git mercurial build-essential unzip python-software-properties ruby curl python-dev htop vim vim-nox dtach dos2unix preload")

def setup_timezone():
    logger = logging.getLogger("%s.setup_timezone" % (APP_NAME, ))
    logger.debug("entry.")
    sudo("mv /etc/localtime /etc/localtime.backup")
    sudo("ln -sf /usr/share/zoneinfo/UTC /etc/localtime")

    # !!AI This fails on Linode Ubuntu 11.10. Why?
    with settings(warn_only=True):
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
    with settings(warn_only=True):
        sudo("apt-get install libc6-dev-i386")
    with cd("~"):
        run("rm -rf redis-2.4.5*")
        run("wget http://redis.googlecode.com/files/redis-2.4.5.tar.gz")
        run("tar xvf redis-2.4.5.tar.gz")
    with cd("~/redis-2.4.5"):
        run("make 32bit")
        sudo("make install")
    with cd("~"):
        run("rm -rf redis-2.4.5*")

def init_redis():
    """ Reference:
        http://library.linode.com/databases/redis/ubuntu-10.04-lucid """
    logger = logging.getLogger("%s.init_redis" % (APP_NAME, ))
    logger.debug("entry.")

    sudo("adduser --system --no-create-home --disabled-login --disabled-password --group redis")
    sudo("mkdir -p /usr/local/redis")
    sudo("chown -R redis:redis /usr/local/redis")
    sudo("touch /var/log/redis.log")
    sudo("chown redis:redis /var/log/redis.log")

    redis_conf_filepath = os.path.join(os.path.dirname(__file__), "redis.conf")
    assert(os.path.isfile(redis_conf_filepath))
    put(redis_conf_filepath, "/usr/local/redis/redis.conf", use_sudo=True)
    sudo("chown redis:redis /usr/local/redis/redis.conf")

    redis_initd_script = os.path.join(os.path.dirname(__file__), "init-deb-redi.sh")
    assert(os.path.isfile(redis_initd_script))
    put(redis_initd_script, "/etc/init.d/redis", use_sudo=True)
    sudo("chmod +x /etc/init.d/redis")
    sudo("update-rc.d -f redis defaults")

    sudo("/etc/init.d/redis start")

def install_postgresql():
    logger = logging.getLogger("%s.install_postgresql" % (APP_NAME, ))
    logger.debug("entry.")

    # !!AI This repo is causing problems on Linode Ubuntu 11.10, so don't do it.
    #sudo(r"add-apt-repository ppa:pitti/postgresql")

    sudo("apt-get update")
    sudo("yes yes | apt-get install postgresql-9.1 libpq-dev postgresql-contrib-9.1 postgresql-common")
    sudo("easy_install -U psycopg2")
    sudo("rm -rf /tmp/tmp*")

def init_postgresql():
    logger = logging.getLogger("%s.init_postgresql" % (APP_NAME, ))
    logger.debug("entry")
    sudo("echo -e \"password\\npassword\" | passwd postgres")
    sudo("rm -f /var/lib/postgresql/.bash_profile")
    sudo("echo export PATH=${PATH}:/usr/lib/postgresql/9.1/bin >> /var/lib/postgresql/.bash_profile", user="postgres")

    # Window condition, if the initdb command fails postgres can no longer stop within a main
    # directory. So just make one and don't crash if it already exists.
    #
    # Another oddity with either PostgreSQL 9.1 or Ubuntu 11.10. The default installation
    # is now owned by root rather than postgres, so try to stop using both users.
    with settings(warn_only=True):
        sudo("mkdir -p /var/lib/postgresql/9.1/main")
        sudo("service postgresql stop", user="postgres")
        sudo("service postgresql stop")
    sudo("rm -rf /var/lib/postgresql/9.1/main")
    sudo("/usr/lib/postgresql/9.1/bin/initdb -D /var/lib/postgresql/9.1/main", user="postgres")
    if not exists(r"/var/lib/postgresql/9.1/main/server.crt", use_sudo = True):
        sudo("ln -s /etc/ssl/certs/ssl-cert-snakeoil.pem /var/lib/postgresql/9.1/main/server.crt")
    if not exists(r"/var/lib/postgresql/9.1/main/server.key", use_sudo = True):
        sudo("ln -s /etc/ssl/private/ssl-cert-snakeoil.key /var/lib/postgresql/9.1/main/server.key")
    sudo("service postgresql start", user="postgres")

    sudo("createuser -s ubuntu", user="postgres")
    sudo("createdb helpmeshop", user="postgres")

    # !!AI PostgreSQL 9.1 changed how to install contrib modules! Instead of
    # directly executing the SQL files you need to use the CREATE EXTENSION
    # command. OK.
    contrib_names = ["adminpack", "hstore", "pgcrypto", "uuid-ossp"]
    for contrib_name in contrib_names:
        run("psql -d helpmeshop -c 'CREATE EXTENSION \"%s\";'" % (contrib_name, ))
    #run("psql -d helpmeshop -f /usr/share/postgresql/9.1/contrib/adminpack.sql")
    #run("psql -d helpmeshop -f /usr/share/postgresql/9.1/contrib/hstore.sql")
    #run("psql -d helpmeshop -f /usr/share/postgresql/9.1/contrib/pgcrypto.sql")
    #run("psql -d helpmeshop -f /usr/share/postgresql/9.1/contrib/uuid-ossp.sql")

    run("psql -d template1 -c \"ALTER USER postgres WITH PASSWORD 'password';\"")
    run("psql -d template1 -c \"ALTER USER ubuntu WITH PASSWORD 'password';\"")

def setup_python():
    logger = logging.getLogger("%s.setup_python" % (APP_NAME, ))
    logger.debug("entry.")
    with cd("~"):
        run("curl -O http://python-distribute.org/distribute_setup.py")
        sudo("python distribute_setup.py")
        run("rm -f distribute*")
    modules = ["httplib2",
               "boto",
               "fabric",
               "colorama",
               "twisted",
               "cython",
               "pycrypto",
               "tornado",
               "momoko",
               "pycket",
               "redis",
               "python-memcached",
               "paramiko",
               "supervisor"]
    sudo("easy_install -U %s" % (" ".join(modules), ))
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

def setup_haproxy():
    logger = logging.getLogger("%s.setup_haproxy" % (APP_NAME, ))
    logger.debug("entry.")

    haproxy_conf_filepath = os.path.join(os.path.dirname(__file__), "haproxy.conf")
    assert(os.path.isfile(haproxy_conf_filepath))
    put(haproxy_conf_filepath, "/home/ubuntu/helpmeshop/infrastructure/haproxy.conf")

    banner_filepath = os.path.join(os.path.dirname(__file__), "haproxyd")
    assert(os.path.isfile(banner_filepath))
    put(banner_filepath, "/etc/init.d/haproxyd", use_sudo=True)
    sudo("chmod +x /etc/init.d/haproxyd")
    sudo("update-rc.d -f haproxyd defaults")

def start_haproxy():
    logger = logging.getLogger("%s.setup_haproxy" % (APP_NAME, ))
    logger.debug("entry.")
    with settings(warn_only=True):
        sudo("/etc/init.d/haproxyd stop")
    sudo("/etc/init.d/haproxyd start")

def start_nginx():
    logger = logging.getLogger("%s.start_nginx" % (APP_NAME, ))
    logger.debug("entry.")
    with settings(warn_only=True):
        sudo("/etc/init.d/nginx stop")
    sudo("/etc/init.d/nginx start")

def install_ack():
    logger = logging.getLogger("%s.install_ack" % (APP_NAME, ))
    logger.debug("entry.")
    sudo("curl -L http://cpanmin.us | perl - --sudo App::cpanminus")
    sudo("cpanm App::Ack")

def install_pypy():
    logger = logging.getLogger("%s.install_pypy" % (APP_NAME, ))
    logger.debug("entry.")
    with cd("~"):
        run("rm -rf pypy-1.7-linux*")
        run("wget https://bitbucket.org/pypy/pypy/downloads/pypy-1.7-linux.tar.bz2")
        run("tar xvf pypy-1.7-linux.tar.bz2")
        sudo("mv pypy-1.7 /usr/local/")
        sudo("ln -s /usr/local/pypy-1.7/bin/pypy /usr/local/bin/pypy")
        run("rm -rf pypy-1.7*")

def harden():
    """ References:
        https://help.ubuntu.com/community/Security
    """
    logger = logging.getLogger("%s.harden" % (APP_NAME, ))
    logger.debug("entry.")

    # ------------------------------------------------------------------------
    # Set up stronger SSH defaults.
    # https://help.ubuntu.com/community/StricterDefaults
    # - No root login.
    # - No password login.
    # - Add our public key to the remote authorize_keys file
    # - Grace login time to 20 seconds
    # - Install SSH banner.
    # ------------------------------------------------------------------------
    sed(filename = "/etc/ssh/sshd_config",
        before = "PermitRootLogin yes",
        after = "PermitRootLogin no",
        use_sudo = True)

    sed(filename = "/etc/ssh/sshd_config",
        before = "PasswordAuthentication yes",
        after = "PasswordAuthentication no",
        use_sudo = True)
    uncomment(filename = "/etc/ssh/sshd_config",
              regex = "PasswordAuthentication no",
              use_sudo = True)
    assert(os.path.isfile(OPENSSH_AUTHORIZED_KEY_FILE))
    with open(OPENSSH_AUTHORIZED_KEY_FILE) as f:
        authorized_key_line = f.readline().strip()
    if not contains(filename = "~/.ssh/authorized_keys",
                    text = authorized_key_line):
        append(filename = "~/.ssh/authorized_keys",
               text = authorized_key_line)

    sed(filename = "/etc/ssh/sshd_config",
        before = "LoginGraceTime.*",
        after = "LoginGraceTime 20",
        use_sudo = True)
    uncomment(filename = "/etc/ssh/sshd_config",
              regex = "Banner \/etc\/issue.net",
              use_sudo = True)
    banner_filepath = os.path.join(os.path.dirname(__file__), "banner.txt")
    assert(os.path.isfile(banner_filepath))
    put(banner_filepath, "/etc/banner.net", use_sudo=True)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    # Set up firewall.
    #
    # Show rules:
    # sudo iptables -L -t nat
    #
    # !!AI Is using iptables to redirect to user-bindable ports and then
    # running nginx / haproxy as non-root users the best way of doing this?
    # Or is this overkill? For now don't do this.
    # ------------------------------------------------------------------------
    sudo("yes yes | apt-get install ufw")
    sudo("yes yes | ufw disable")
    sudo("yes yes | ufw reset --force")

    sudo("ufw limit ssh")
    sudo("ufw allow ntp")

    sudo("ufw allow www")
    #sudo("iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080")
    #sudo("ufw allow 8080/tcp")

    sudo("ufw allow https")
    #sudo("iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 6000")
    #sudo("ufw allow 8443/tcp")

    sudo("ufw default deny")
    sudo("yes yes | ufw enable")
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    # Set up denyhosts.
    # ------------------------------------------------------------------------
    sudo("yes yes | apt-get install denyhosts")
    sudo("cp /etc/denyhosts.conf /etc/denyhosts.conf.backup")
    sed(filename = "/etc/denyhosts.conf",
        before = "AGE_RESET_VALID.*=.*",
        after = "AGE_RESET_VALID=10m",
        use_sudo = True)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    # Make shared memory read-only
    # https://help.ubuntu.com/community/StricterDefaults
    # ------------------------------------------------------------------------
    append(filename = "/etc/fstab",
           text = "tmpfs     /dev/shm     tmpfs     defaults,ro     0     0",
           use_sudo = True)
    sudo("mount -o remount /dev/shm/")
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Put on hardened sysctl.conf
    # ------------------------------------------------------------------------
    sysctl_conf_filepath = os.path.join(os.path.dirname(__file__), "sysctl.conf")
    assert(os.path.isfile(sysctl_conf_filepath))
    put(sysctl_conf_filepath, "/etc/sysctl.conf", use_sudo=True)
    # ------------------------------------------------------------------------

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
           text = "export PATH=${PATH}:/usr/lib/postgresql/9.1/bin:/usr/local/bin")

def setup_vim():
    logger = logging.getLogger("%s.setup_vim" % (APP_NAME, ))
    logger.debug("entry.")

    vimrc_filepath = os.path.join(os.path.dirname(__file__), "vim", ".vimrc")
    assert(os.path.isfile(vimrc_filepath))
    put(vimrc_filepath, "~/.vimrc")

    vim_path = os.path.join(os.path.dirname(__file__), "vim", "*")
    #assert(os.path.isdir(vim_path))
    run("rm -rf ~/vim")
    run("mkdir -p ~/.vim")
    put(vim_path, "~/.vim/")
    run("rm -f ~/.vim/.vimrc")

    sudo("yes yes | sudo apt-get install ruby-dev")
    with cd("~/.vim/ruby/command-t"):
        run("ruby extconf.rb")
        run("make clean")
        run("make")

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
        run("echo '10000002' > serial")
        run("touch index.txt")

        # Root CA key.
        run("export OPENSSL_CONF=~/myCA/caconfig.cnf; openssl req -x509 -newkey rsa:4096 -out cacert.pem -outform PEM -days 1825")

        # Self-signed root CA certificate.
        run("openssl x509 -in cacert.pem -out cacert.crt")

        run("export OPENSSL_CONF=~/myCA/exampleserver.cnf; openssl req -newkey rsa:4096 -keyout tempkey.pem -keyform PEM -out tempreq.pem -outform PEM")
        run("openssl rsa < tempkey.pem > server_key.pem")

        run("export OPENSSL_CONF=~/myCA/caconfig.cnf; openssl ca -in tempreq.pem -out server_crt.pem")
        run("rm -f tempkey.pem && rm -f tempreq.pem")

        run("openssl x509 -in cacert.pem -out cacert.crt")
        run("openssl x509 -in server_crt.pem -out server_crt.crt")
        #run("openssl x509 -in server_key.pem -out server_key.crt")

def setup_hostname():
    """ Reference:
        http://library.linode.com/getting-started#sph_set-the-hostname
    """
    logger = logging.getLogger("%s.setup_hostname" % (APP_NAME, ))
    logger.debug("entry.")
    sudo("echo %s > /etc/hostname" % (REMOTE_HOSTNAME, ))
    sudo("hostname -F /etc/hostname")
    if exists("/etc/default/dhcpcd",
              use_sudo = True):
        comment("/etc/default/dhcpcd",
                "SET_HOSTNAME.*=.*yes",
                use_sudo = True)
    #!!AI Add 127.0.0.1 <hostname> to /etc/hosts
    #!!AI Add <public IP address> <hostname> to /etc/hosts

def install_nginx():
    # ------------------------------------------------------------------------
    #   Also harden nginx by not displaying version information in
    #   responses.
    #
    #   Reference: http://www.cyberciti.biz/tips/linux-unix-bsd-nginx-webserver-security.html
    # ------------------------------------------------------------------------
    logger = logging.getLogger("%s.install_nginx" % (APP_NAME, ))
    logger.debug("entry.")
    sudo("yes yes | apt-get install libpcre3-dev build-essential libssl-dev zlib1g zlib1g-dev")
    with cd("~"):
        run("rm -rf nginx-1.1.12*")
        run("wget http://nginx.org/download/nginx-1.1.12.tar.gz")
        run("tar xvf nginx-1.1.12.tar.gz")
    with cd("~/nginx-1.1.12"):
        sed(filename = "./src/http/ngx_http_header_filter_module.c",
            before = "\"Server: nginx\"",
            after = "\"Server: Web Server\"")
        sed(filename = "./src/http/ngx_http_header_filter_module.c",
            before = "\"Server: \" NGINX_VER",
            after = "\"Server: Web Server\"")
        cc_flags = ["-O2", "-fstack-protector-all", "-fexceptions", "-D_FORTIFY_SOURCE=2", "--param=ssp-buffer-size=4"]
        modules = ["--with-http_gzip_static_module"]
        run("./configure --user=nginx --group=nginx --with-http_ssl_module --with-pcre-jit --with-cc-opt=\"%s\" %s" % (" ".join(cc_flags), " ".join(modules)))
        run("make")
        sudo("make install")
    with cd("~"):
        run("rm -rf nginx-1.1.12*")
    sudo("adduser --system --no-create-home --disabled-login --disabled-password --group nginx")

def setup_nginx():
    logger = logging.getLogger("%s.setup_nginx" % (APP_NAME, ))
    logger.debug("entry.")

    sudo("chown -R nginx:nginx /usr/local/nginx")

    nginx_conf_filepath = os.path.join(os.path.dirname(__file__), "nginx.conf")
    assert(os.path.isfile(nginx_conf_filepath))
    put(nginx_conf_filepath, "/usr/local/nginx/conf/nginx.conf", use_sudo=True)
    sudo("chown nginx:nginx /usr/local/nginx/conf/nginx.conf")

    nginx_initd_script = os.path.join(os.path.dirname(__file__), "init-deb-nginx.sh")
    assert(os.path.isfile(nginx_initd_script))
    put(nginx_initd_script, "/etc/init.d/nginx", use_sudo=True)
    sudo("chmod +x /etc/init.d/nginx")
    sudo("update-rc.d -f nginx defaults")

def call_fabric_function(function, remote_host, *args, **kwds):
    if KEY_FILENAME is not None:
        with settings(host_string=remote_host,
                      user=REMOTE_USERNAME,
                      key_filename=KEY_FILENAME,
                      password=REMOTE_PASSWORD):
            function(*args, **kwds)
    else:
        assert(REMOTE_PASSWORD is not None)
        with settings(host_string=remote_host,
                      user=REMOTE_USERNAME,
                      password=REMOTE_PASSWORD):
            function(*args, **kwds)

def main():
    logger.info("Starting main.  args: %s" % (sys.argv[1:], ))

    REMOTE_HOST = REMOTE_IP_ADDRESS
    REMOTE_PORT = REMOTE_SSH_PORT
    if len(sys.argv) >= 2:
        REMOTE_HOST = sys.argv[1]
    if len(sys.argv) >= 3:
        REMOTE_PORT = sys.argv[2]
    colorama.init()
    REMOTE_HOST = "%s:%s" % (REMOTE_HOST, REMOTE_PORT)
    logger.debug("REMOTE_HOST: %s" % (REMOTE_HOST, ))

    # ------------------------------------------------------------------
    #   What functions to call.  Uncomment / comment as you wish.
    #   In theory only call these functions once per installation,
    #   but safe, albeit wasteful, to run again.
    # ------------------------------------------------------------------
    functions_to_call = [ \
                         #setup_hostname,
                         #setup_timezone,
                         #install_bare_essentials,
                         #install_erlang,
                         #install_redis,
                         #init_redis,
                         #install_memcached,
                         #install_haproxy,
                         #install_nginx,
                         #install_ack,
                         #install_pypy,
                         #setup_python,
                         #setup_ntp,
                         #install_postgresql,
                         #init_postgresql,
                         #checkout_code,
                         #harden,
                         #setup_bash_profile,
                         setup_vim,
                         #setup_ssl,
                         #setup_haproxy,
                         #start_haproxy,
                         #setup_nginx,
                         #start_nginx,
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


