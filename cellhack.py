import os
import re
from mitmproxy import http
from get_hosts import scrape_hosts
import subprocess


def start():
    # ask user for input
    user_in = input(
        "Select strategy:  \n 1. Host-spoofing \n 2. Mac-spoofing \n")
    if user_in != "1" and user_in != "2":
        print("Invalid input")
        start()
    if user_in == "1":
        url = input("Enter URL: ")
        if cell_hack(url) == False:
            print("Method unsuccessful")
            user_in = input("Try  Mac-spoofing (y/n)\n")
    else:
        print("Mac spoofing")
        # call bash script mac_spoof.sh
        # os.system("./mac_spoof.sh")


def cell_hack(url):
    # call the function check_network and return 0 if the execution takes more than 1 second
    data = scrape_hosts(url)
    links = parse_string(data[1], r'(http|https):\/\/[^\s]*')
    hosts = data[0]
    for link in links:
        for host in hosts:
            print(host)
            send_request(link, host)
            if check_network() == 0:
                return print("Connection successful")
    return False


def check_network():
    host = "www.google.com"
    ping = subprocess.Popen(
        ["ping", "-c", "4", host],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    # returns 0 ping was unsuccessful
    out, error = ping.communicate()
    return ping.returncode


def send_request(link, hostname):
    reply = os.system("curl -H 'Host: " + hostname +
                      "' " + link + ' >/dev/null 2>&1')


def parse_string(str, regex):
    data = []
    for key in str:
        # get substring of key that matches regex
        data.append(re.search(regex, key).group(0))
    return data


start()
