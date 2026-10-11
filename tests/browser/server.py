from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
root=Path(__file__).resolve().parents[2]
class Handler(SimpleHTTPRequestHandler):
 def translate_path(self,path):
  if path.startswith('/station_meteo/images/test-arrow.svg'):
   return str(root/'custom_components/station_meteo/frontend/compass-assets/arrow-feathers.svg')
  if path.startswith('/station_meteo/images/test-cloud.webp'):
   return str(root/'tests/browser/sample-cloud.webp')
  if path.startswith('/station_meteo/images/'):
   return str(root/'custom_components/station_meteo/frontend/weather-icons/cloudy.webp')
  if path.startswith('/station_meteo/frontend/'):
   return str(root/'custom_components/station_meteo/frontend'/path.split('/station_meteo/frontend/',1)[1].split('?')[0])
  return str(root/'tests/browser'/path.split('?',1)[0].lstrip('/')) if path!='/' else str(root/'tests/browser/index.html')
 def log_message(self,*args):pass
ThreadingHTTPServer(('127.0.0.1',8765),Handler).serve_forever()
