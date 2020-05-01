import pythondcspro as pythondcs
import datetime, configparser, textwrap, argparse
from operator import itemgetter

# Shortcut functions
MACasHex = pythondcs.macint_to_hex
MACasInt = pythondcs.machex_to_int

def MACConv(MACstr):
  return '.'.join([MACstr.replace(':', '').lower()[i:i+4] for i in range(0, 12, 4)])

def GetTimes(idc):
  if idc not in IDCs: return "\n"
  else: return IDCs[idc]['lastConnectedTime']

def ListIDCs(outputstring, MACList):
  global FullOutput
  FullOutput+='<br><table><caption>'+outputstring+'</caption><tr><th>MAC</th><th>Name</th><th>Ip Address</th><th>Last Online</th></tr>'
  if len(MACList) == 0:
    outputstring = '<tr><td colspan="4" style="text-align: center">-- None --</td></tr>'
    FullOutput+=outputstring
  for IDC in sorted(MACList, key=GetTimes):
    if IDC in IDCs:
      HexMAC = MACasHex(IDC)
      DotMAC = MACConv(HexMAC)
      outputstring = '<tr><td><a href="{NetDiagUrl}{MACLINK}">{MAC}</a></td><td><a href="{DCSurl}/idcs/{NameLink}">{Name}</a></td><td>{Ip}</td><td>{Time:%Y-%m-%d %H:%M:%S}</td></tr>'.format(NetDiagUrl=NetDiagUrl, MACLINK=DotMAC, MAC=HexMAC, DCSurl=DCSurl, NameLink=IDC, Name=IDCs[IDC]["name"], Ip=IDCs[IDC]['ipAddress'], Time=datetime.datetime.strptime(IDCs[IDC]['lastConnectedTime'].replace("Z","+0000"), "%Y-%m-%dT%H:%M:%S%z").astimezone())
      FullOutput+=outputstring
    else:
      outputstring = '<tr><td>{MAC}</td><td colspan="3" style="text-align: center">Not found in the database</td></tr>'.format(MAC=MACasHex(IDC))
      FullOutput+=outputstring
  FullOutput+='</table><br>'

def ListDevices(outputstring, IDList):
  global FullOutput
  FullOutput+='<br><table><caption>'+outputstring+'</caption><tr><th>Database ID</th><th>IDC MAC</th><th>IDC Name</th><th>Description</th><th>Serial Number</th><th>Modbus ID</th></tr>'
  if len(IDList) == 0:
    outputstring = '<tr><td colspan="6" style="text-align: center">-- None --</td></tr>'
    FullOutput+=outputstring
  for Dev in sorted(IDList):
    if Dev in AllSuspectDevices:
      MacInt = int(AllSuspectDevices[Dev]['macAddress'])
      IDC = MACasHex(MacInt)
      outputstring = '<tr><td>{ID}</td><td>{MAC}</td><td><a href="{DCSurl}/idcs/{NameLink}">{Name}</a></td><td>{Desc}</td><td>{SN}</td><td>{Addr}</td></tr>'.format(DCSurl=DCSurl, ID=AllSuspectDevices[Dev]['id'], MAC=IDC, NameLink=MacInt, Name=IDCs[MacInt]["name"], Desc=AllSuspectDevices[Dev]['description'], SN=AllSuspectDevices[Dev]['serialNumber'], Addr=AllSuspectDevices[Dev]['address'])
      FullOutput+=outputstring
    else:
      outputstring = '<tr><td>{ID}</td><td colspan="5" style="text-align: center">Not found in the database</td></tr>'.format(ID=Dev)
      FullOutput+=outputstring
  FullOutput+='</table><br>'

def GetConnectedIdcInformation():
  try:
    print("Getting IDC list...", end=' ')
    Response = dcs.get_idcs()
    IDCs = { idc['macAddress'] : idc for idc in Response }
    print("{} found".format(len(IDCs)))
  except pythondcs.requests.RequestException as weberr:
    print("Failed: {}".format(weberr))
    IDCs = {}
  return IDCs

def GetModbusDevicesByIdc(MAC):
  try:
    print("Getting devices for IDC {}...".format(MACasHex(MAC)), end=' ')
    Response = dcs.get_modbus_devices_by_idc(MAC)
    Devices = { Dev['id'] : Dev for Dev in Response }
    print("{} found".format(len(Devices)))
  except pythondcs.requests.RequestException as weberr:
    print("Failed: {}".format(weberr))
    Devices = {}
  return Devices

parser = argparse.ArgumentParser(description="Checks DCS Server for Offline devices")
parser.add_argument("cfg", action='store', metavar=__file__+'.ini', nargs="?", default=__file__+'.ini', type=argparse.FileType('r+t'), help="Path to configuration file")
args = parser.parse_args()

cfg=configparser.RawConfigParser()
cfgfile=args.cfg
cfg.read_file(cfgfile)

now = datetime.datetime.now(datetime.timezone.utc)
try:
  lastrun = datetime.datetime.strptime(cfg.get('DATA', 'run'), '%Y-%m-%d %H:%M:%S.%f%z')
except ValueError:
  lastrun = now

print("Time of execution is: ", now)
cfg.set('DATA', 'run', now.strftime('%Y-%m-%d %H:%M:%S.%f%z'))

DCSurl = cfg.get('DCS', 'url')
NetDiagUrl = cfg.get('DCS', 'netdiagurl')

dcs = pythondcs.DCSSession(DCSurl, cfg.get('DCS', 'username'), cfg.get('DCS', 'password'))

IDCs = GetConnectedIdcInformation()

ignoredIDCscfg = cfg.get('DATA', 'ignoredIDCs')
ignoredIDCs = set([ MACasInt(id) for id in ignoredIDCscfg.split(',') ] if ignoredIDCscfg != '' else [])

PrevOfflineIDCscfg = cfg.get('DATA', 'offlineIDCs')
PrevOfflineIDCs = set([ MACasInt(id) for id in PrevOfflineIDCscfg.split(',') ] if PrevOfflineIDCscfg != '' else [])

OfflineIDCs = { i for i in IDCs if datetime.datetime.strptime(IDCs[i]['lastConnectedTime'].replace("Z","+0000"), "%Y-%m-%dT%H:%M:%S%z") < lastrun } - ignoredIDCs
OfflineIDCsNow = OfflineIDCs-PrevOfflineIDCs
DevicesStillOfflineIDCs = PrevOfflineIDCs & OfflineIDCs
DevicesNowOnlineIDCs = PrevOfflineIDCs - OfflineIDCs

cfg.set('DATA', 'offlineIDCs', ','.join(map(MACasHex, sorted(OfflineIDCs))))
cfg.set('DATA', 'ignoredIDCs', ','.join(map(MACasHex, sorted(ignoredIDCs))))

print("Getting list of key Devices...")
AllSuspectDevices={}
for IDC in ( IDCs[idc]["macAddress"] for idc in IDCs if IDCs[idc]["swVersion"].startswith("4") and IDCs[idc]["modbusDeviceCount"] > 0 and IDCs[idc]["deviceStatusSummary"] != "online" ):
  AllSuspectDevices.update(GetModbusDevicesByIdc(IDC))

dcs.logout()
del dcs

PrevOfflinecfg = cfg.get('DATA', 'offlinedevices')
PrevOffline = set([ int(id) for id in PrevOfflinecfg.split(',') ] if PrevOfflinecfg != '' else [])

IgnoredDevicescfg = cfg.get('DATA', 'ignoreddevices')
IgnoredDevices = set([ int(id) for id in IgnoredDevicescfg.split(',') ] if IgnoredDevicescfg != '' else [])

KeyOfflineDevices = { Dev for Dev in AllSuspectDevices if AllSuspectDevices[Dev]['status'] == "offline" and AllSuspectDevices[Dev]['deviceType'] != "modbusMeter" }-IgnoredDevices
OfflineDevicesNow = KeyOfflineDevices-PrevOffline
DevicesStillOffline = PrevOffline & KeyOfflineDevices
DevicesNowOnline = PrevOffline - KeyOfflineDevices

cfg.set('DATA', 'offlinedevices', ','.join(map(str, sorted(KeyOfflineDevices))))
cfg.set('DATA', 'ignoreddevices', ','.join(map(str, sorted(IgnoredDevices))))

print()
FullOutput='<!DOCTYPE html><html><head><style>table {{border-collapse: collapse; width: 100%}} table, th, td {{ border: 1px solid black; }} th, td {{ padding: 5px; text-align: left; }} caption {{ font-weight: bold; text-align: left; }} tr:nth-child(even) {{background-color: #f2f2f2}} tr:hover {{background-color: #cccccc}} th {{ background-color: #808080; color: white;}}</style></head><body><b><p>Checks run at: {:%Y-%m-%d %H:%M:%S}<br>Last Checks run at: {:%Y-%m-%d %H:%M:%S} ({:.1f} minutes ago)</p></b>'.format(now.astimezone(), lastrun.astimezone(), (now-lastrun).total_seconds()/60.0)

if len(OfflineIDCsNow) != 0: ListIDCs('*** New Offline IDCs found ***', OfflineIDCsNow)
if len(DevicesStillOfflineIDCs) != 0: ListIDCs('Existing Offline IDCs since last check', DevicesStillOfflineIDCs)
if len(DevicesNowOnlineIDCs) != 0: ListIDCs('IDCs now appear to be back online', DevicesNowOnlineIDCs)
if cfg.getboolean('EMAIL', 'showignored'): ListIDCs('The following IDCs are being ignored', ignoredIDCs)

if len(OfflineDevicesNow) != 0: ListDevices('*** New Offline Devices found ***', OfflineDevicesNow)
if len(DevicesStillOffline) != 0: ListDevices('Existing Offline Devices since last check'.format(lastrun, (now-lastrun).total_seconds()/60.0), DevicesStillOffline)
if len(DevicesNowOnline) != 0: ListDevices('Devices now appear to be back online'.format(lastrun, (now-lastrun).total_seconds()/60.0), DevicesNowOnline)
if cfg.getboolean('EMAIL', 'showignored'): ListDevices('The following Devices are being ignored', IgnoredDevices)

FullOutput+='</body></html>'

#print(FullOutput)

if cfg.getboolean('EMAIL', 'enabled') and (len(OfflineDevicesNow) != 0  or len(DevicesNowOnline) != 0 or len(OfflineIDCsNow) != 0  or len(DevicesNowOnlineIDCs) != 0 or cfg.getboolean('EMAIL', 'alwayssend')):
  import smtplib
  from email.mime.text import MIMEText
  msg = MIMEText('\r\n'.join(textwrap.wrap(FullOutput, width=998, break_on_hyphens=False)), 'html')
  msg['From']=cfg.get('EMAIL', 'from')
  emailto = [ppl.strip() for ppl in cfg.get('EMAIL', 'to').split(',')]
  msg['To']=','.join(emailto)
  cfg.set('EMAIL', 'to', msg['To'])
  emailcc = [ppl.strip() for ppl in cfg.get('EMAIL', 'cc').split(',')]
  msg['Cc']=','.join(emailcc)
  cfg.set('EMAIL', 'cc', msg['Cc'])
  emailbcc = [ppl.strip() for ppl in cfg.get('EMAIL', 'bcc').split(',')]
  cfg.set('EMAIL', 'bcc', ','.join(emailbcc))
  msg['Subject']='Offline Devices'
  print("\nEmailing results to: {}".format(msg['To']))
  if cfg.getboolean('SMTP', 'SSL'):
    server = smtplib.SMTP_SSL(cfg.get('SMTP', 'server'), cfg.getint('SMTP', 'port'))
  else:
    server = smtplib.SMTP(cfg.get('SMTP', 'server'), cfg.getint('SMTP', 'port'))
  try:
    if cfg.getboolean('SMTP', 'auth'): server.login(cfg.get('SMTP', 'username'), cfg.get('SMTP', 'password'))
    emailmsg = msg.as_string()
    server.sendmail(msg['From'], emailto+emailcc+emailbcc, emailmsg)
    server.quit()
    print("Email Sent!")
    try:
      with open(cfg.get('FILES','email',fallback=__file__+'.email'), 'wt') as dump:
        dump.write(emailmsg)
    except Exception as fail:
      print('Failed to save email:', fail)
  except Exception as fail:
    print('Failed to send email:', fail)
else:
  print("\nNo email sent since nothing has changed (or it was disabled)!")

try:
  with open(cfg.get('FILES','html',fallback=__file__+'.html'), 'wt') as dump:
    dump.write(FullOutput)
except Exception as fail:
    print('Failed to save html:', fail)

cfgfile.seek(0)
cfg.write(cfgfile)
cfgfile.truncate()
cfgfile.close()
