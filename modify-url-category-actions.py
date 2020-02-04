###############################################################################
#
# Script:       modify-url-category-actions.py
#
# Author:       Chris Goodwin <cgoodwin@paloaltonetworks.com>
#
# Description:  This script allows a user to modify actions in bulk for any
#               predefined or custom URL category across multiple URL filtering
#               profiles within a device group on Panorama
#
# Usage:        modify-url-category-actions.py
#
# Requirements: requests
#
# Python:       Version 3
#
###############################################################################
###############################################################################


import getpass
import re
import time
from xml.etree import ElementTree as ET
try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except ImportError:
    raise ValueError('requests support not available, please install module')


###############################################################################
###############################################################################


# Prompts the user to enter an address, then checks it's validity
def getfwipfqdn():
    while True:
        fwipraw = input("\nPlease enter Panorama IP or FQDN: ")
        ipr = re.match(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$", fwipraw)
        fqdnr = re.match(r"(?=^.{4,253}$)(^((?!-)[a-zA-Z0-9-]{1,63}(?<!-)\.)+[a-zA-Z]{2,63}$)", fwipraw)
        if ipr:
            break
        elif fqdnr:
            break
        else:
            print("\nThere was something wrong with your entry. Please try again...\n")
    return fwipraw


# Prompts the user to enter a username and password
def getCreds():
    while True:
        username = input("Please enter your user name: ")
        usernamer = re.match(r"^[\w-]{3,24}$", username)
        if usernamer:
            password = getpass.getpass("Please enter your password: ")
            break
        else:
            print("\nThere was something wrong with your entry. Please try again...\n")
    return username, password


# Retrieves the user's api key
def getkey(fwip):
    while True:
        try:
            fwipgetkey = fwip
            username, password = getCreds()
            keycall = "https://%s/api/?type=keygen&user=%s&password=%s" % (fwipgetkey, username, password)
            r = requests.get(keycall, verify=False)
            tree = ET.fromstring(r.text)
            if tree.get('status') == "success":
                apikey = tree[0][0].text
                break
            else:
                print("\nYou have entered an incorrect username or password. Please try again...\n")
        except requests.exceptions.ConnectionError:
            print("\nThere was a problem connecting to the firewall. Please check the address and try again...\n")
            exit()
    return apikey


# Presents the user with a choice of device-groups
def getDG(baseurl, mainkey):
    dgXmlUrl = "/api/?type=config&action=get&xpath=/config/devices/entry[@name='localhost.localdomain']/device-group&key="
    dgFullUrl = (baseurl + dgXmlUrl + mainkey)
    r = requests.get(dgFullUrl, verify=False)
    dgfwTree = ET.fromstring(r.text)
    dgList = []
    for entry in dgfwTree.findall('./result/device-group/entry'):
        dgList.append(entry.get('name'))
    while True:
        try:
            print('\n\nHere\'s a list of device groups found in Panorama...\n')
            i = 1
            for dgName in dgList:
                if i < 10:
                    print('%s)  %s' % (i, dgName))
                else:
                    print('%s) %s' % (i, dgName))
                i += 1
            dgChoice = int(input('\nChoose a number for the device-group\n\nAnswer: '))
            reportDG = dgList[dgChoice - 1]
            break
        except:
            print("\n\nThat's not a number in the list, try again...\n")
            time.sleep(1)
    return reportDG


# Retriev parent device groups
def getParentDGs(devGroup, baseurl, mainkey):
    dgHierarchyURL = baseurl + '/api/?type=op&cmd=<show><dg-hierarchy></dg-hierarchy></show>&key=' + mainkey
    r = requests.get(dgHierarchyURL, verify=False)
    dgHierarychyTree = ET.fromstring(r.text)
    return [dg.get('name') for dg in dgHierarychyTree.findall(".//*/[@name='%s']..." % (devGroup))]


# Split URL profile entries
def splitUrlProfileEntries(indexString, profileList):
    profileList_Indexes = re.sub(r'\s+', '', indexString).split(',')
    profileList_Indexes_ranges = []
    rangePattern = re.compile(r'-')
    for i in profileList_Indexes[:]:
        if rangePattern.findall(i):
            profileList_Indexes_ranges.append(i)
            profileList_Indexes.remove(i)
    profileList_Indexes = list(map(int, profileList_Indexes))
    rangeCheck = True
    for i in profileList_Indexes_ranges:
        x = list(map(int, i.split('-')))
        if x[0] > x[1]:
            rangeCheck = False
            badRange = str(x[0]) + '-' + str(x[1])
        y = range(x[0], x[1] + 1)
        for z in y:
            profileList_Indexes.append(z)
    if rangeCheck:
        profileList_Indexes.sort()
        profileList_Indexes = list(set(profileList_Indexes[:]))
        profileList_Indexes_Length = len(profileList_Indexes)
        print()
        if profileList_Indexes[profileList_Indexes_Length - 1] > len(profileList):
            time.sleep(1)
            print("\n\nYour entry was found to have a number that was out of range for the number of URL filtering profiles contained within the device group\nThere are a total of " + str(len(profileList)) + " profiles in the device group. Make sure your entries fall within the proper range.")
        else:
            UrlProfileList = []
            for index in profileList_Indexes:
                UrlProfileList.append(profileList[index - 1])
            print('\n\nHere are the URL filtering profiles that you have chosen:\n')
            count = 0
            for x in UrlProfileList:
                print(str(profileList_Indexes[count]) + ') ' + x)
                count += 1
            time.sleep(1)
            return UrlProfileList
    else:
        time.sleep(1)
        print('\n\nYou entered a range incorrectly (%s), please check your list and try again.' % badRange)
    return None


# Presents the user with a choice of security profile groups for the chosen device-group
def getUrlProfiles(devGroup, baseurl, mainkey):
    UrlProfileXmlUrl = "/api/?type=config&action=get&xpath=/config/devices/entry/device-group/entry[@name='%s']/profiles/url-filtering&key=" % (devGroup)
    UrlProfileFullUrl = (baseurl + UrlProfileXmlUrl + mainkey)
    r = requests.get(UrlProfileFullUrl, verify=False)
    UrlProfileFwTree = ET.fromstring(r.text)
    UrlProfileList = [entry.get('name') for entry in UrlProfileFwTree.findall('./result/url-filtering/entry')]
    if UrlProfileList != []:
        while True:
            try:
                print('\n\n\nHere\'s a list of URL filtering profiles found for the %s device group...\n' % (devGroup))
                i = 1
                for UrlProfileName in UrlProfileList:
                    print('%s) %s' % (i, UrlProfileName))
                    i += 1
                print('%s) Apply to all profiles in the device group' % (i))
                while True:
                    UrlProfileChoice = input('\nChoose a number for the URL filtering profile, or choose all\nYou can also enter a comma separated list, with ranges\nExample --> 1, 3, 5-9, 11\n\nAnswer: ')
                    try:
                        if int(UrlProfileChoice) == len(UrlProfileList) + 1:
                            allProfiles = True
                            UrlProfileList_processed = UrlProfileList
                            print("\n\nYou've chosen to apply changes to all URL filtering profiles in the %s\n" % (devGroup))
                            time.sleep(1)
                            return UrlProfileList_processed, allProfiles
                    except ValueError:
                        pass
                    UrlProfileChoice_r = re.match(r"^(((\d{1,5})|(\d{1,5}\s*-\s*\d{1,5}))(\s*,\s*((\d{1,5}\s*)|(\d{1,5}\s*-\s*\d{1,5})))*)$", UrlProfileChoice)
                    if UrlProfileChoice_r:
                        allProfiles = False
                        UrlProfileList_processed = splitUrlProfileEntries(UrlProfileChoice, UrlProfileList)
                        if UrlProfileList_processed is not None:
                            return UrlProfileList_processed, allProfiles
                    else:
                        time.sleep(1)
                        print("\nYour entry wasn't in the proper format. Please enter either single entries or ranges separated by commas,\nor a combination of both. White space can be used, but will be stripped out when parsed.\n")
            except:
                time.sleep(1)
                print("\n\nThat's not a number in the list, try again...\n")
    else:
        time.sleep(1)
        print('\n\nThere were no URL filtering profiles found for the %s device group, please choose another device group...\n' % (devGroup))


# Retrieve the predefined URL categories
def getPredefinedUrlCategories(baseurl, mainkey):
    UrlCatsXmlUrl = "/api/?type=config&action=get&xpath=/config/predefined/pan-url-categories&key="
    UrlCatsFullUrl = (baseurl + UrlCatsXmlUrl + mainkey)
    r = requests.get(UrlCatsFullUrl, verify=False)
    UrlCatsFwTree = ET.fromstring(r.text)
    return sorted([entry.get('name') for entry in UrlCatsFwTree.findall('./result/pan-url-categories/entry')])


# Retrieve the custom categories from the chosen DG and all parent DGs
def getCustomUrlCategories(devGroup, parentDGs, baseurl, mainkey):
    categories = []
    sharedUrlCatsURL = baseurl + '/api/?type=config&action=get&xpath=/config/shared/profiles/custom-url-category&key=' + mainkey
    r = requests.get(sharedUrlCatsURL, verify=False)
    sharedUrlCatsTree = ET.fromstring(r.text)
    for entry in sharedUrlCatsTree.findall('./result/custom-url-category/entry'):
        categories.append(entry.get('name') + ' *')
    for dg in parentDGs:
        parentDgUrlCatsURL = baseurl + "/api/?type=config&action=get&xpath=/config/devices/entry/device-group/entry[@name='%s']/profiles/custom-url-category&key=%s" % (dg, mainkey)
        r = requests.get(parentDgUrlCatsURL, verify=False)
        parentDgUrlCatsTree = ET.fromstring(r.text)
        for entry in parentDgUrlCatsTree.findall('./result/custom-url-category/entry'):
            categories.append(entry.get('name') + ' *')
    dgUrlCatsURL = baseurl + "/api/?type=config&action=get&xpath=/config/devices/entry/device-group/entry[@name='%s']/profiles/custom-url-category&key=%s" % (devGroup, mainkey)
    r = requests.get(dgUrlCatsURL, verify=False)
    dgUrlCatsTree = ET.fromstring(r.text)
    for entry in dgUrlCatsTree.findall('./result/custom-url-category/entry'):
        categories.append(entry.get('name') + ' *')
    return list(sorted(set(filter(lambda x: x is not None, categories))))


# Prompt user to choose a URL category
def chooseUrlCat(catList):
    while True:
        try:
            print("\n\nHere's a list of URL categories found for the device group...\n")
            i = 1
            for cat in catList:
                if i < 10:
                    print('%s)  %s' % (i, cat))
                else:
                    print('%s) %s' % (i, cat))
                i += 1
            catChoice = int(input('\nChoose a number for the URL category\n\nAnswer: '))
            return catList[catChoice - 1].replace(' *', '')     # replace the astrisk that is added to denote a custom URL category
        except:
            print("\n\nThat's not a number in the list, try again...\n")
            time.sleep(1)


# Build the XML elements that are needed for API call
def getUrlProfileElements(UrlCat, UrlAction, UrlProfile, devGroup, baseurl, mainkey):
    elementURL = "%s/api/?type=config&action=get&xpath=/config/devices/entry/device-group/entry[@name='%s']/profiles/url-filtering/entry[@name='%s']&key=%s" % (baseurl, devGroup, UrlProfile, mainkey)
    r = requests.get(elementURL, verify=False)
    tree = ET.fromstring(r.text)
    root = tree.find('.//entry')
    if root.find('credential-enforcement') is not None:
        root.remove(root.find('credential-enforcement'))    # Remove credential enforcement elements, as they are not needed, and cause API push failure
    # Remove current category element
    parent = root.find(".//member[.='%s']..." % (UrlCat))
    element_to_remove = root.find(".//member[.='%s']" % (UrlCat))
    if element_to_remove is not None:
        parent.remove(element_to_remove)
    # Add new category element
    if root.find(UrlAction) is None:
        ET.SubElement(root, UrlAction)
    parent = root.find(UrlAction)
    child = ET.SubElement(parent, 'member')
    child.text = UrlCat
    # Create elements string, remove whitespace and newline characters
    elements = ET.tostring(root).decode("utf-8")
    elements = re.sub(r'\n\s*', '', elements)
    return elements


# Prompt user to choose an action to set for the URL category
def chooseUrlAction(urlCat):
    actions = ['alert', 'allow', 'block', 'continue', 'override']
    while True:
        try:
            print('\n\nChoose which action you would like to set for the %s URL category\n\n1) Alert\n2) Allow\n3) Block\n4) Continue\n5) Override\n' % urlCat)
            actionChoice = int(input('Answer: '))
            return actions[actionChoice - 1]
        except:
            print("\n\nThat's not a number in the list, try again...\n")
            time.sleep(1)


def main():
    fwip = getfwipfqdn()
    mainkey = getkey(fwip)
    baseurl = 'https://' + fwip

    while True:
        devGroup = getDG(baseurl, mainkey)
        parentDGs = getParentDGs(devGroup, baseurl, mainkey)
        predefinedUrlCats = getPredefinedUrlCategories(baseurl, mainkey)
        customUrlCats = getCustomUrlCategories(devGroup, parentDGs, baseurl, mainkey)
        allUrlCats = predefinedUrlCats + customUrlCats
        UrlProfiles, allProfsBool = getUrlProfiles(devGroup, baseurl, mainkey)
        UrlCatChoice = chooseUrlCat(allUrlCats)
        UrlActionChoice = chooseUrlAction(UrlCatChoice)

        if allProfsBool:
            print("\n\n\nConfig is ready to be pushed...\n\nThe action for %s URL filtering category will be changed to '%s' for ALL URL filtering profiles\n" % (UrlCatChoice, UrlActionChoice))
        else:
            print("\n\nConfig is ready to be pushed...\n\nThe action for %s URL filtering category will be changed to '%s' for the following URL filtering profiles:\n%s" % (UrlCatChoice, UrlActionChoice, UrlProfiles))
        input('\n\nHit Enter to continue, or CTRL+C to cancel the script...\n')

        for profile in UrlProfiles:
            xmlElements = getUrlProfileElements(UrlCatChoice, UrlActionChoice, profile, devGroup, baseurl, mainkey)
            applyProfileUrl = "%s/api/?type=config&action=edit&xpath=/config/devices/entry/device-group/entry[@name='%s']/profiles/url-filtering/entry[@name='%s']&element=%s&key=%s" % (baseurl, devGroup, profile, xmlElements, mainkey)
            r = requests.get(applyProfileUrl, verify=False)
            tree = ET.fromstring(r.text)
            if tree.get('status') == 'success':
                print('%s category was successfully changed to %s for the %s URL filtering profile' % (UrlCatChoice, UrlActionChoice, profile))
            else:
                print('\n\nThere was something wrong with an API call that was sent to Panorama\nPlease check the API call below to troubleshoot the issue...\n\n%s' % (applyProfileUrl))
                input('\n\nHit Enter to continue on, or CTRL+C to cancel the script...\n')

        while True:
            runAgain = input("\n\nAll changes have been pushed to the Panorama's %s device group\n\nWould you like to run this script again for the same Panorama? [Y/n]  " % (devGroup))
            if runAgain.lower() == 'y' or runAgain == '':
                break
            elif runAgain.lower() == 'n':
                print('\n\nOk, have a great day!!\n\n')
                exit()
            else:
                print("\nWrong answer, try a 'y' or 'n' this time...")


if __name__ == '__main__':
    main()
