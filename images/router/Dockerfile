FROM 34334/labs:base

#install vrrpd, lldpd and quagga
RUN apt-get install -y lldpd quagga openssh-server
RUN apt-get install -y geany nano mousepad

#add the quagga scripts
ADD daemons /etc/quagga/daemons
USER quagga
ADD ospfd.conf /etc/quagga/ospfd.conf
ADD zebra.conf /etc/quagga/zebra.conf

USER root
ADD sshd_config /etc/ssh/sshd_config

#add supervisord script and startup script and disable initial dhclient
#ADD start_vrrpd.py /start_vrrpd.py
#ADD supervisor_vrrpd.conf /etc/supervisor/conf.d/supervisor_vrrpd.conf
RUN service ssh start
RUN touch /home/cybertek .XAuthority
RUN rm -f /etc/supervisor/conf.d/supervisor_dhclient.conf
