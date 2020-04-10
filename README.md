# DCSOfflineChecker
 Checks and reports on IDCs and other devices which are offline via DCSv3 server

This utility checks DCS for the online/offline status all IDC devices, and for newer IDCv4 devices, checks all modbus devices which are not meters (i.e. pulse loggers and radio receivers).
It provides an HTML output of what it found to be offline since it last checked, what is still offline, and also what devices were previously offline which are now back online. This HTML output is then optionally emailed.

This utility was originally created for use at the University of Warwick (by Mark Jarvis as a personal project) and so contains some specific customisations, such as permitting links to network diagnostic pages.

This was also originally written in Python 2 for DCSv2 servers using a SOAP/XML interface back in 2016, but in 2019, it was ported to Python 3 and DCSv3 servers using [`pythondcs`](https://github.com/jarvisms/pythondcs). In 2020, it got published to GitHub!