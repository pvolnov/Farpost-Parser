import re
import time

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from selenium import webdriver

from config import SELENOID_ADRESS, RU_CAPTCHA_APY_KEY
from models import Items, Tasks

driver = webdriver.Remote(
    command_executor=SELENOID_ADRESS,
    desired_capabilities={
        "browserName": "chrome",
        "sessionTimeout": "2h"
    }
)


def pass_captcha():
    driver.find_element_by_id("grecap-fallback").click()
    driver.find_element_by_tag_name("img").screenshot("captcha.jpg")

    with open("captcha.jpg", "rb") as f:
        task_id = requests.post("https://rucaptcha.com/in.php",
                                data={
                                    "key": RU_CAPTCHA_APY_KEY
                                }, files={
                "file": f
            }
                                ).text[3:]

    print(f"Get captcha ID {task_id}")
    captcha_text = ""
    while "OK" not in captcha_text:
        time.sleep(2)
        captcha_text = requests.get("https://rucaptcha.com/res.php",
                                    params={
                                        "key": "3e12df6ed3a4c0e9e7b2c951bb2c9c51",
                                        "action": "get",
                                        "id": task_id
                                    }).text
    captcha_text = captcha_text[3:]
    print(f"Get captcha result: {captcha_text}")

    driver.find_element_by_name("g-recaptcha-response").send_keys(captcha_text)
    driver.find_element_by_id("send-button").click()
    time.sleep(1)


def cl(text):
    return re.sub(r"[\n\t\s]+", " ", text)


def parse(url):
    time.sleep(2)

    driver.get(url)
    soup = BeautifulSoup(driver.page_source, 'html5lib')
    for s in soup.find_all("script"):
        s.extract()

    data = {
        "url": url,
        "articul": url.split('-')[-1][:-5]
    }
    info = {}
    for field in soup.find_all("div", {"class": "field"}):
        info[field.div.text.replace("\n", "")] = re.sub("[\xa0\s]+", " ", field.span.text)
    data['params'] = info
    if soup.find("span", {"itemprop": "price"}):
        data['price'] = soup.find("span", {"itemprop": "price"}).text

    data['subpart'] = soup.find_all("li", {"itemprop": "itemListElement"})[-2].span.text

    data['about'] = re.sub(r"[\n\t]+", "\n", soup.find("div", {"class": "bulletinText"}).text)
    data['date'] = cl(soup.find("span", {"class": "viewbull-header__actuality"}).text)
    data['is_agency'] = soup.find("span", {"data-field": "isAgency"}).text
    data['name'] = soup.h1.span.text
    data['saller_login'] = soup.find("span", {"class": "userNick"}).a.text
    data['saller_url'] = "https://www.farpost.ru" + soup.find("span", {"class": "userNick"}).a['href']

    comp = soup.find("h3", {"class": "company-name"})
    if comp:
        data['company'] = comp.a.text

    driver.get(f"https://www.farpost.ru/bulletin/{data['articul']}/ajax_contacts?paid=1&ajax=1")
    s2 = BeautifulSoup(driver.page_source, 'html5lib')
    s2.find("script").extract()
    data['saller_contacts'] = re.sub(r"[\n\t]+", "\n", s2.text)
    return data


if __name__ == "__main__":

    while True:
        tasks = Tasks.select().where(Tasks.done == False).execute()
        for t in tqdm(tasks):
            if Items.get_or_none(Items.url == t.url) is None:
                try:
                    it = parse(t.url)
                except Exception as e:
                    print(t.url, e)
                    continue

                it['tag'] = t.tag
                Items.create(**it)
            t.done = True
            t.save()
