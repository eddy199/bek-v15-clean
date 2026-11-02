import urllib.request
import json
url="https://api.b.ai/v1/models"
key="sk-1jxap19uxogiyci5y4etlh2psshbttkz"
req=urllib.request.Request(url,headers={"Authorization":f"Bearer {key}"})
try:
 print(json.loads(urllib.request.urlopen(req).read().decode()))
except Exception as e:
 print(e)