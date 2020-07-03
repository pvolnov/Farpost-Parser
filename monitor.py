import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from peewee import fn
from tqdm import tqdm
from selenium import webdriver

from config import SELENOID_ADRESS, RU_CAPTCHA_APY_KEY
from models import Items, Tasks
import tgbot

driver = webdriver.Remote(
    command_executor=SELENOID_ADRESS,
    desired_capabilities={
        "browserName": "chrome",
        "sessionTimeout": "5m"
    }
)


# driver = webdriver.Firefox()


def get_captcha_ans(filename="captcha.png"):
    with open(filename, "rb") as f:
        task_id = requests.post("https://rucaptcha.com/in.php",
                                data={
                                    "key": RU_CAPTCHA_APY_KEY
                                }, files={"file": f}
                                ).text[3:]

    print(f"Get captcha ID {task_id}")
    captcha_text = ""
    while "OK" not in captcha_text:
        time.sleep(3)
        captcha_text = requests.get("https://rucaptcha.com/res.php",
                                    params={
                                        "key": "3e12df6ed3a4c0e9e7b2c951bb2c9c51",
                                        "action": "get",
                                        "id": task_id
                                    }).text
        if captcha_text == "ERROR_CAPTCHA_UNSOLVABLE":
            return False, task_id

    captcha_text = captcha_text[3:]
    print(f"Get captcha result: {captcha_text}")
    return captcha_text, task_id


def pass_captcha(page):
    if "recaptcha" not in page:
        return True

    try:
        driver.find_element_by_id("grecap-fallback").click()
    except:
        pass

    driver.find_element_by_tag_name("img").screenshot("captcha.png")

    captcha_text, task_id = get_captcha_ans()
    if not captcha_text:
        return pass_captcha(page)

    driver.find_element_by_name("g-recaptcha-response").send_keys(captcha_text)
    driver.find_element_by_id("send-button").click()
    time.sleep(2)
    if "Вы не робот?" in driver.page_source:
        r = requests.get("https://rucaptcha.com/res.php",
                         params={
                             "key": RU_CAPTCHA_APY_KEY,
                             "action": "reportbad",
                             "id": task_id
                         })
        print("recaptcha is incorrect:", r.text)
        return False
    return True


def pass_captcha_contacts(soup):
    if not soup.find("img", {"class": "bzr-captcha__image"}):
        return soup

    print("find contacts captcha")
    driver.find_element_by_class_name("bzr-captcha__image").screenshot("captcha.png")
    captcha_text, task_id = get_captcha_ans()
    if not captcha_text:
        return pass_captcha_contacts(soup)

    driver.find_element_by_name("captcha_code").send_keys(captcha_text)
    driver.find_element_by_xpath("//div[@class='captcha-button-wrap']/input[@value='Показать контакты']").click()
    time.sleep(1)

    soup = BeautifulSoup(driver.page_source, 'html5lib')
    if soup.find("img", {"class": "bzr-captcha__image"}):
        r = requests.get("https://rucaptcha.com/res.php",
                         params={
                             "key": RU_CAPTCHA_APY_KEY,
                             "action": "reportbad",
                             "id": task_id
                         })
        print("recaptcha is incorrect:", r.text)
        return pass_captcha_contacts(soup)

    return soup


def cl(text):
    return re.sub(r"[\n\t\s]+", " ", text)


def parse(url):
    time.sleep(1)

    driver.get(url)
    page = driver.page_source
    soup = BeautifulSoup(page, 'html5lib')
    captcha = False
    while not pass_captcha(page):
        captcha = True

    if captcha:
        soup = BeautifulSoup(driver.page_source, 'html5lib')

    for s in soup.find_all("script"):
        s.extract()

    data = {
        "url": url,
        "articul": url.split('-')[-1][:-5]
    }
    info = {}
    for field in soup.find_all("div", {"class": "field"}):
        if field.span and field.div:
            info[field.div.text.replace("\n", "")] = re.sub(r"[\xa0\s]+", " ", field.span.text)
    data['params'] = info

    price = soup.find("span", {"itemprop": "price"})
    if price:
        data['price'] = price.text

    if len(soup.find_all("li", {"itemprop": "itemListElement"})) > 2:
        sp = soup.find_all("li", {"itemprop": "itemListElement"})[-2]
        if sp.span:
            data['subpart'] = sp.span.text

    ab = soup.find("div", {"class": "bulletinText"})
    if ab:
        data['about'] = re.sub(r"[\n\t]+", "\n", ab.text)

    date = soup.find("span", {"class": "viewbull-header__actuality"})
    if date:
        data['date'] = cl(date.text)

    agent = soup.find("span", {"data-field": "isAgency"})
    if agent:
        data['is_agency'] = agent.text

    name = soup.h1
    if name and name.span:
        data['name'] = name.span.text

    nik = soup.find("span", {"class": "userNick"})
    if nik and nik.a:
        data['saller_login'] = nik.a.text
        data['saller_url'] = "https://www.farpost.ru" + nik.a['href']

    comp = soup.find("h3", {"class": "company-name"})
    if comp and comp.a:
        data['company'] = comp.a.text

    for i in range(3):
        try:
            driver.find_element_by_link_text("Показать контакты").click()
        except:
            continue
        time.sleep(1)
        soup = BeautifulSoup(driver.page_source, 'html5lib')

        soup = pass_captcha_contacts(soup)
        contacts = soup.find("div", {"class": "new-contacts dummy-listener_new-contacts"})
        if contacts:
            data['saller_contacts'] = re.sub(r"[\n\t]+", "\n", contacts.text)
            break

    return data


if __name__ == "__main__":
    while True:
        tasks = Tasks.select().where(Tasks.done == False).order_by(fn.Random()).execute()
        print("tasks", len(tasks))
        for t in tqdm(tasks):
            t.done = True
            t.save()

            item = Items.get_or_none(Items.url == t.url)
            if item:
                if item.saller_contacts == "" or "captcha" in item.saller_contacts:
                    Items.delete_by_id(item.id)
                else:
                    item.deleted = False
                    item.save()
                    continue
            try:
                it = parse(t.url)
            except Exception as e:
                print(t.url, e)
                continue

            it['tag'] = t.tag
            if "saller_contacts" not in it or "captcha" in it['saller_contacts']:
                print(it['url'], "saller_contacts empty")
                continue

            Items.create(**it)

        time.sleep(180)
        now = datetime.now()
        if now.day % 7 == 0 and now.hour == 0 and now.minute < 4:
            tgbot.update_tasks()

        driver.refresh()
