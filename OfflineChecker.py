import pythondcspro as pythondcs
import datetime, configparser, textwrap, argparse
import smtplib
from email.mime.text import MIMEText

# Definition of the short code and friendly name for each device type
deviceTypes = {"modbusMeter":("M","Modbus Meter"), "pulseCounter":("P","Pulse Counter"),"radioReceiver":("R","Radio Receiver")}

# Shortcut functions
MACasHex = pythondcs.macint_to_hex

def MACasInt(MaxHex):
  """Converts a Hex MAC into an Integer, or None if that doesn't work"""
  try:
    return pythondcs.machex_to_int(MaxHex)
  except (TypeError,ValueError,AssertionError) as err:
    print(err)
    return None

def MACConv(MACstr):
  """Converts MAC string from 01:23:45:67:89:AB to 0123.4567.89ab"""
  return '.'.join([MACstr.replace(':', '').lower()[i:i+4] for i in range(0, 12, 4)])

def GetTimes(idc):
  """Fetches Last Connected Time for a given IDC (int) or returned line return if not found"""
  try: return IDCs[idc]['lastConnectedTime']
  except KeyError: return "\n"

def DeviceAddress(idcslave):
  """For a given tuple of (idc,slave), both in integer form, return a nicely formatted address including the device typ, such as 01:23:45:67:89:AB-P100"""
  idc, slave = idcslave
  try:
    addr = f"{MACasHex(idc)}-{deviceTypes[IDCs[idc]['modbusDevices'][slave]['deviceType']][0]}{slave}"
  except KeyError:
    addr = f"{MACasHex(idc)}-{slave}"
  return addr

def GetDevice(addr):
  """Converts a formatted device address such as 01:23:45:67:89:AB-P100 back into a tuple of (idc,slave) in integer form. The letter before the slave address may be M, P, R (upper or lower case) or omitted"""
  try:
    addrsplit = addr.split("-")
    if len(addrsplit) == 2:
      mac = MACasInt(addrsplit[0])
      slave = int(float(addrsplit[1].strip("MPRmpr")))
      return (mac,slave)
    else:
      raise ValueError(f'Incorrectly formatted address: "{addr}"')
  except (TypeError,ValueError,AssertionError) as err:
    print(err)
    return (None,None)

def ListIDCs(outputstring, MACList):
  """Produces a table of details for a given 'MACList' with 'outputstring' as a caption/title"""
  global FullOutput
  FullOutput+='<br><table><caption>'+outputstring+'</caption><tr><th>MAC</th><th>Name</th><th>Ip Address</th><th>Last Online</th></tr>'
  if len(MACList) == 0:
    outputstring = '<tr><td colspan="4" style="text-align: center">-- None --</td></tr>'
    FullOutput+=outputstring
  for IDC in sorted(MACList, key=GetTimes):
    if IDC in IDCs:
      HexMAC = MACasHex(IDC)
      DotMAC = MACConv(HexMAC)
      outputstring = '<tr><td><a href="{NetDiagUrl}{MACLINK}{NetDiagSuffix}">{MAC}</a></td><td><a href="{DCSurl}/idcs/{NameLink}">{Name}</a></td><td>{Ip}</td><td>{Time}</td></tr>'.format(NetDiagUrl=NetDiagUrl, MACLINK=DotMAC, NetDiagSuffix=NetDiagSuffix, MAC=HexMAC, DCSurl=DCSurl, NameLink=IDC, Name=IDCs[IDC]["name"], Ip=IDCs[IDC]['ipAddress'], Time=IDCs[IDC]['lastConnectedTime'].strftime('%Y-%m-%d %H:%M:%S') if IDCs[IDC]['lastConnectedTime'] is not None else "Unknown")
      FullOutput+=outputstring
    else:
      outputstring = '<tr><td>{MAC}</td><td colspan="3" style="text-align: center">Not found in the database</td></tr>'.format(MAC=MACasHex(IDC))
      FullOutput+=outputstring
  FullOutput+='</table><br>'

def ListDevices(outputstring, DevList):
  """Produces a table of details for a given 'DevList' with 'outputstring' as a caption/title"""
  global FullOutput
  FullOutput+='<br><table><caption>'+outputstring+'</caption><tr><th>Device Address</th><th>IDC Name</th><th>Device Type</th><th>Description</th><th>Serial Number</th><th>Last Status Change</th></tr>'
  if len(DevList) == 0:
    outputstring = '<tr><td colspan="6" style="text-align: center">-- None --</td></tr>'
    FullOutput+=outputstring
  for Dev in sorted(DevList):
    MacInt, slave = Dev
    try:
      HexMAC = MACasHex(MacInt)
      IDCDetails = IDCs[MacInt]
      DevDetails = IDCDetails['modbusDevices'][slave]
      outputstring = '<tr><td>{addr}</td><td><a href="{DCSurl}/idcs/{MacInt}">{Name}</a></td><td>{type}</td><td>{Desc}</td><td>{SN}</td><td>{Time}</td></tr>'.format(DCSurl=DCSurl, addr=DeviceAddress(Dev), MAC=HexMAC, MacInt=MacInt, Name=IDCDetails["name"], type=deviceTypes[DevDetails['deviceType']][1], Desc=DevDetails['description'], SN=DevDetails['serialNumber'], Time=DevDetails['statusTimestamp'].strftime('%Y-%m-%d %H:%M:%S') if DevDetails['statusTimestamp'] is not None else "Unknown")
    except KeyError:
      outputstring = '<tr><td>{addr}</td><td colspan="5" style="text-align: center">Details not retreived</td></tr>'.format(addr=DeviceAddress(Dev))
    FullOutput+=outputstring
  FullOutput+='</table><br>'

def GetConnectedIdcInformation():
  """Fetches list of all IDCs and their details, but only if not Disabled in DCS"""
  try:
    print("Getting IDC list...", end=' ')
    Response = dcs.get_idcs()
    IDCs = { idc['macAddress'] : idc for idc in Response if idc["isDisabled"] == False }
    for idc in IDCs:
      if IDCs[idc]['lastConnectedTime'] is not None:
        IDCs[idc]['lastConnectedTime'] = datetime.datetime.strptime(IDCs[idc]['lastConnectedTime'].replace("Z","+0000"), "%Y-%m-%dT%H:%M:%S%z")
    print("{} found".format(len(IDCs)))
  except pythondcs.requests.RequestException as weberr:
    print("Failed: {}".format(weberr))
    IDCs = {}
  return IDCs

def GetModbusDevicesByIdc(MAC):
  """Returns a Dict of Offline devices for a given IDC keyed by slave address"""
  try:
    print("Getting devices for IDC {}...".format(MACasHex(MAC)), end=' ')
    Response = dcs.get_modbus_devices_by_idc(MAC)
    Devices = { Dev['address'] : Dev for Dev in Response }
    for Dev in Devices:
      if Devices[Dev]['statusTimestamp'] is not None:
        Devices[Dev]['statusTimestamp'] = datetime.datetime.strptime(Devices[Dev]['statusTimestamp'].replace("Z","+0000"), "%Y-%m-%dT%H:%M:%S%z")
    print(f"{len(Devices)} offline device(s) found")
  except pythondcs.requests.RequestException as weberr:
    print("Failed: {}".format(weberr))
    Devices = {}
  return Devices

# Command Line Argument Parser
parser = argparse.ArgumentParser(description="Checks DCS Server for Offline devices")
parser.add_argument("cfg", action='store', metavar=__file__+'.ini', nargs="?", default=__file__+'.ini', type=argparse.FileType('r+t'), help="Path to configuration file")
args = parser.parse_args()

# Config File Loader
cfg=configparser.RawConfigParser()
cfgfile=args.cfg
cfg.read_file(cfgfile)

# Timestamp
now = datetime.datetime.now(datetime.timezone.utc)
try:
  lastrun = datetime.datetime.strptime(cfg.get('DATA', 'run'), '%Y-%m-%d %H:%M:%S.%f%z')
except ValueError:
  lastrun = now
print("Time of execution is: ", now)
cfg.set('DATA', 'run', now.strftime('%Y-%m-%d %H:%M:%S.%f%z'))

# Get Login Details and timeouts
DCSurl = cfg.get('DCS', 'url')
IDCTimeout = datetime.timedelta(minutes = cfg.getint('DCS', 'idctimeout', fallback=30))
DevTimeout = datetime.timedelta(minutes = cfg.getint('DCS', 'devtimeout', fallback=30))
NetDiagUrl = cfg.get('NETDIAG', 'linkurl')
NetDiagSuffix = cfg.get('NETDIAG', 'suffix')

# Get IDC lists from config
ignoredIDCscfg = cfg.get('DATA', 'ignoredIDCs')
ignoredIDCs = set([ MACasInt(id) for id in ignoredIDCscfg.split(',') ] if ignoredIDCscfg != '' else [])
ignoredIDCs.discard(None)
PrevOfflineIDCscfg = cfg.get('DATA', 'offlineIDCs')
PrevOfflineIDCs = set([ MACasInt(id) for id in PrevOfflineIDCscfg.split(',') ] if PrevOfflineIDCscfg != '' else [])
PrevOfflineIDCs.discard(None)

# Get Device lists from config
PrevOfflineDevicescfg = cfg.get('DATA', 'offlinedevices')
PrevOfflineDevices = set([ GetDevice(addr) for addr in PrevOfflineDevicescfg.split(',') ] if PrevOfflineDevicescfg != '' else [])
PrevOfflineDevices.discard((None,None))
IgnoredDevicescfg = cfg.get('DATA', 'ignoreddevices')
IgnoredDevices = set([ GetDevice(addr) for addr in IgnoredDevicescfg.split(',') ] if IgnoredDevicescfg != '' else [])
IgnoredDevices.discard((None,None))

# Get Data from DCS
dcs = pythondcs.DCSSession(DCSurl, cfg.get('DCS', 'username'), cfg.get('DCS', 'password'))
IDCs = GetConnectedIdcInformation()
print("Getting list of key Devices...")
for idc in IDCs:
  IDCs[idc]['modbusDevices'] = GetModbusDevicesByIdc(idc) if (IDCs[idc]["swVersion"].startswith("4") and IDCs[idc]["modbusDeviceCount"] > 0 and IDCs[idc]["deviceStatusSummary"] != "online") or (idc in {dev[0] for dev in IgnoredDevices | PrevOfflineDevices}) else {}
dcs.logout()
del dcs

# Assess IDCs and Devices and save
OfflineIDCs = { i for i in IDCs if ( IDCs[i]['lastConnectedTime'] is None or IDCs[i]['lastConnectedTime'] < (now - IDCTimeout) )} - ignoredIDCs
OfflineIDCsNow = OfflineIDCs-PrevOfflineIDCs
DevicesStillOfflineIDCs = PrevOfflineIDCs & OfflineIDCs
DevicesNowOnlineIDCs = PrevOfflineIDCs - OfflineIDCs

KeyOfflineDevices = { (idc,slave) for idc in IDCs for slave in IDCs[idc]['modbusDevices'] if IDCs[idc]['modbusDevices'][slave]['deviceType'] != "modbusMeter" and IDCs[idc]['modbusDevices'][slave]['status'] == "offline" and ( IDCs[idc]['modbusDevices'][slave]['statusTimestamp'] is None or IDCs[idc]['modbusDevices'][slave]['statusTimestamp'] < (now - DevTimeout) )}-IgnoredDevices
OfflineDevicesNow = KeyOfflineDevices-PrevOfflineDevices
DevicesStillOffline = PrevOfflineDevices & KeyOfflineDevices
DevicesNowOnline = PrevOfflineDevices - KeyOfflineDevices

# Save results
cfg.set('DATA', 'offlineIDCs', ','.join(map(MACasHex, sorted(OfflineIDCs))))
cfg.set('DATA', 'ignoredIDCs', ','.join(map(MACasHex, sorted(ignoredIDCs))))
cfg.set('DATA', 'offlinedevices', ','.join(map(DeviceAddress, sorted(KeyOfflineDevices))))
cfg.set('DATA', 'ignoreddevices', ','.join(map(DeviceAddress, sorted(IgnoredDevices))))

print() # Print blank space for clarity

# Prepare html output
FullOutput='<!DOCTYPE html><html><head><style>table {{border-collapse: collapse; width: 100%}} table, th, td {{ border: 1px solid black; }} th, td {{ padding: 5px; text-align: left; }} caption {{ font-weight: bold; text-align: left; }} tr:nth-child(even) {{background-color: #f2f2f2}} tr:hover {{background-color: #cccccc}} th {{ background-color: #808080; color: white;}}</style></head><body><b><p>Checks run at: {:%Y-%m-%d %H:%M:%S}<br>Last Checks run at: {:%Y-%m-%d %H:%M:%S} ({:.1f} minutes ago)<br>IDC Timeout: {:n} minutes, Device Timeout: {:n} minutes</p></b>'.format(now.astimezone(), lastrun.astimezone(), (now-lastrun).total_seconds()/60.0, IDCTimeout.total_seconds()/60.0, DevTimeout.total_seconds()/60.0)

if len(OfflineIDCsNow) != 0: ListIDCs('*** New Offline IDCs found ***', OfflineIDCsNow)
if len(DevicesStillOfflineIDCs) != 0: ListIDCs('Existing Offline IDCs since last check', DevicesStillOfflineIDCs)
if len(DevicesNowOnlineIDCs) != 0: ListIDCs('IDCs now appear to be back online', DevicesNowOnlineIDCs)
if cfg.getboolean('EMAIL', 'showignored'): ListIDCs('The following IDCs are being ignored', ignoredIDCs)

if len(OfflineDevicesNow) != 0: ListDevices('*** New Offline Devices found ***', OfflineDevicesNow)
if len(DevicesStillOffline) != 0: ListDevices('Existing Offline Devices since last check', DevicesStillOffline)
if len(DevicesNowOnline) != 0: ListDevices('Devices now appear to be back online', DevicesNowOnline)
if cfg.getboolean('EMAIL', 'showignored'): ListDevices('The following Devices are being ignored', IgnoredDevices)

FullOutput+='</body></html>'

# Send email if required

if cfg.getboolean('EMAIL', 'enabled') and (len(OfflineDevicesNow) != 0  or len(DevicesNowOnline) != 0 or len(OfflineIDCsNow) != 0  or len(DevicesNowOnlineIDCs) != 0 or cfg.getboolean('EMAIL', 'alwayssend')):
  msg = MIMEText('\r\n'.join(textwrap.wrap(FullOutput, width=998, break_on_hyphens=False)), 'html')
  msg['From']=cfg.get('EMAIL', 'from')
  msg['To']=','.join( [ppl.strip() for ppl in cfg.get('EMAIL', 'to').split(',')] )
  cfg.set('EMAIL', 'to', msg['To'])
  msg['Cc']=','.join( [ppl.strip() for ppl in cfg.get('EMAIL', 'cc').split(',')] )
  cfg.set('EMAIL', 'cc', msg['Cc'])
  msg['Bcc'] = ','.join( [ppl.strip() for ppl in cfg.get('EMAIL', 'bcc').split(',')] )
  cfg.set('EMAIL', 'bcc', msg['Bcc'])
  msg['Subject']='Offline Devices'
  print("\nEmailing results to: {}".format(msg['To']))
  if cfg.getboolean('SMTP', 'SSL'):
    server = smtplib.SMTP_SSL(cfg.get('SMTP', 'server'), cfg.getint('SMTP', 'port'))
  else:
    server = smtplib.SMTP(cfg.get('SMTP', 'server'), cfg.getint('SMTP', 'port'))
  try:
    if cfg.getboolean('SMTP', 'auth'): server.login(cfg.get('SMTP', 'username'), cfg.get('SMTP', 'password'))
    server.send_message(msg)
    server.quit()
    print("Email Sent!")
    try:
      with open(cfg.get('FILES','email',fallback=__file__+'.email'), 'wt') as dump:
        dump.write(msg.as_string())
    except Exception as fail:
      print('Failed to save email:', fail)
  except Exception as fail:
    print('Failed to send email:', fail)
else:
  print("\nNo email sent since nothing has changed (or it was disabled)!")

# Store html output
try:
  with open(cfg.get('FILES','html',fallback=__file__+'.html'), 'wt') as dump:
    dump.write(FullOutput)
except Exception as fail:
    print('Failed to save html:', fail)

# Store config details
cfgfile.seek(0)
cfg.write(cfgfile)
cfgfile.truncate()
cfgfile.close()
