import datetime
import json
import os
import pickle
import random
import re
import time

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from tqdm import tqdm

from models import Items, Tasks

# urls = Items.select(Items.url).where(Items.saller_contacts.contains("captcha")).execute()
# urls = [u.url for u in urls]
#
# Tasks.update({Tasks.done:False}).where(Tasks.url.in_(urls)).execute()
# n = Items.select().where(
#     Items.saller_contacts.contains("captcha")).count()
#
# print(n)
# with open("saller_contacts.txt", "r") as f:
#     for line in tqdm(f.readlines()):
#         d = json.loads(line[:-1])
#         u = Items.get_by_id(d['id'])
#         u.saller_contacts = d['saller_contacts']
#         u.save()
#
print(datetime.datetime.now().day)
print(datetime.datetime.now().hour)
print(datetime.datetime.now().minute)
exit(0)

countries = """Albania			Japan
Argentina		Latvia
Australia		Luxembourg
Austria			Malaysia
Belgium			Mexico
Bosnia_And_Herzegovina	Moldova
Brazil			Netherlands
Bulgaria		New_Zealand
Canada			North_Macedonia
Chile			Norway
Costa_Rica		Poland
Croatia			Portugal
Cyprus			Romania
Czech_Republic		Serbia
Denmark			Singapore
Estonia			Slovakia
Finland			Slovenia
France			South_Africa
Georgia			South_Korea
Germany			Spain
Greece			Sweden
Hong_Kong		Switzerland
Hungary			Taiwan
Iceland			Thailand
India			Turkey
Indonesia		Ukraine
Ireland			United_Kingdom
Israel			United_States
Italy			Vietnam"""

countries = re.split(r"\s+", countries)
cid = 0
driver = webdriver.Firefox()
items = Items.select().where(Items.saller_contacts.contains("captcha")).limit(1000).execute()
print(Items.select().where(Items.saller_contacts.contains("captcha")).count())
users = []

for i in tqdm(items):
    driver.get(i.url)
    try:
        driver.find_element_by_link_text("Показать контакты").click()
        time.sleep(1)
        soup = BeautifulSoup(driver.page_source, 'html5lib')

        if "Объявление не найдено" in soup:
            saller_contacts = ""
            continue
        if soup.find("div", {"class": "new-contacts dummy-listener_new-contacts"}):
            saller_contacts = re.sub(r"[\n\t]+", "\n",
                                     soup.find("div", {"class": "new-contacts dummy-listener_new-contacts"}).text)

    except Exception as e:
        if "captcha" in driver.page_source:
            os.system(f"nordvpn c {countries[cid]}")
            print("New ip", countries[cid])
            cid += 1
            driver.delete_all_cookies()
            driver.refresh()
            continue
        else:
            saller_contacts = ""
            print(e)

    with open("saller_contacts.txt", "a") as f:
        f.write(json.dumps({
            "id": i.id,
            "saller_contacts": saller_contacts
        }) + "\n")
