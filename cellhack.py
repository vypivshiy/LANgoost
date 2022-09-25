import os
import re
from mitmproxy import http
from get_hosts import scrape_hosts
import subprocess

additional_hosts = ["Origin"]
# npm install spoof -g


def start():
    # ask user for input
    user_in = input(
        "Select strategy:  \n 1) Cell Hack \n 2) Mac-spoofing \n")
    if user_in != "1" and user_in != "2":
        print("Invalid input")
        start()
    if user_in == "1":
        url = input("########################\nEnter URL: ")
        if cell_hack(url) == False:
            print("Method unsuccessful")
            user_in = input("Try  Mac-spoofing (y/n)\n")
    else:
        if input("Are you using Linux? (y/n)\n") == "n":
            print("########################\nMac spoofing")
            user_in = input(
                "select method:  \n 1. Spoof Mac address \n 2. Scan for mac addresses in your network \n")
            if user_in != "1" and user_in != "2":
                print("Invalid input")
                start()
            if user_in == "1":
                address = input("Enter Mac address: \n")
                print("spoofing:")
                return os.system("sudo spoof set " + address + "en0 ")
                print("done")
                os.system("sudo spoof list --wifi")
            else:
                url = input("Enter ip: ")
                os.system("sudo nmap -sS " + url)
                print("copy desired Mac address")
                address = input("Enter Mac address: \n")
                print("spoofing:")
                os.system("sudo spoof set " + address + "en0")
                os.system("sudo spoof list --wifi")
        else:
            os.system("chmod +x mac-spoof.sh")
            os.system("./mac_spoof.sh")


def cell_hack(url):
    # call the function check_network and return 0 if the execution takes more than 1 second
    data = scrape_hosts(url)
    links = parse_string(data[1], r'(http|https):\/\/[^\s]*')
    hosts = list(data[0])
    hosts = hosts + additional_hosts
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
