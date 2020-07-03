import requests
import telebot
from bs4 import BeautifulSoup
from playhouse.shortcuts import model_to_dict
from telebot import types
import pandas as pd
from config import telegram_bot_key, BOT_PASS
from models import Items, Tasks

bot = telebot.TeleBot(telegram_bot_key)


class btns:
    RWNTA = "Объявления по аренде помещений ⬇️"
    SELL_ROOM = "Объявления по продаже помещений ⬇️"
    SELL_FLAT = "Объявления по продаже квартир ⬇️"


parsels_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                             row_width=1)
parsels_keyboard.add(
    types.KeyboardButton(text=btns.RWNTA),
    types.KeyboardButton(text=btns.SELL_ROOM),
    types.KeyboardButton(text=btns.SELL_FLAT),
)


def get_url_from_section(url):
    r = requests.get(url).text
    soup = BeautifulSoup(r, 'html5lib')
    count = int(soup.find("span", {"id": "itemsCount_placeholder"})['data-count'])
    res = []
    for p in range(1, count // 50 + 1):
        r = requests.get(url, params={
            "page": p
        }).text
        soup = BeautifulSoup(r, 'html5lib')
        urls = soup.find_all("a", {"class": "bulletinLink bull-item__self-link auto-shy"})
        urls = ["https://www.farpost.ru" + u['href'] for u in urls]
        urls = list(filter(lambda x: "html" in x, urls))

        res += urls
    return list(set(res))


def update_tasks():
    urls = []
    for tag in ["rent_business_realty", "sell_business_realty", "sell_flats"]:
        urs = get_url_from_section(f"https://www.farpost.ru/vladivostok/realty/{tag}/")
        urls += urs
        tasks = [{
            "url": u,
            "tag": tag
        } for u in urs]
        Tasks.insert_many(tasks).on_conflict_ignore().execute()
        print(tag, ":done")

    Items.update({Items.deleted: True}).where(Items.url.not_in(urls))


@bot.message_handler(commands=['start', 'status', 'parser_begin'])
def start(message):
    print("New commands:", message.text)
    if message.text == "/start":
        bot.send_message(message.chat.id, "Пришлите пароль для активации бота")

    elif message.text == "/status":
        done = Tasks.select().where(Tasks.done == True).count()
        all = Tasks.select().count()
        if all == 0:
            bot.send_message(message.chat.id, "Идет сбор сслылок на объявления...")
            return

        progress = round((done / all) * 30)
        percent = round((done / all) * 100)
        mes = f"Done: {percent}% ({done}/{all})\n\n[" + "=" * progress + (">" if percent < 100 else "") + "_" * (
                30 - progress) + "]"
        bot.send_message(message.chat.id, mes)

    elif message.text == "/parser_begin":
        if Tasks.select().where(Tasks.done == False).count() > 10:
            bot.send_message(message.chat.id, "Дождитесь окончания тякущего сеанса парсера")
            return

        Tasks.delete().execute()
        update_tasks()
        bot.send_message(message.chat.id,
                         "Запущен парсинг, для отслеживания состояния парсера отправьте команду /status")


@bot.message_handler(content_types=['text'])
def text(message):
    print(message.text)
    if message.text == BOT_PASS:
        bot.send_message(message.chat.id,
                         "Бот активирован",
                         reply_markup=parsels_keyboard)
        return

    elif message.text == btns.RWNTA:
        tag = "rent_business_realty"
    elif message.text == btns.SELL_ROOM:
        tag = "sell_business_realty"
    elif message.text == btns.SELL_FLAT:
        tag = "sell_flats"
    else:
        return
    bot.send_message(message.chat.id,
                     "Начали готовить для вас файлы")

    items = Items.select().where((Items.tag == tag) & (Items.deleted == False)).execute()
    print(f"For sended {tag}: {len(items)}")
    items = [model_to_dict(i) for i in items]

    def preparing_data(i):
        return {
            "ссылка на объявление": i['url'],
            "текст объявления": i['about'],
            "дата размещения": i['date'],
            "контакты": i['saller_contacts'] if i['saller_contacts'][0] != '\n' else i['saller_contacts'][1:],
            "логин разместившего": i['saller_login'],
            "предложение": i['is_agency'],
            "компания": i['company'],
            **i['params']
        }

    if tag == "rent_business_realty":
        from collections import defaultdict
        data_by_tags = defaultdict(list)
        for i in items:
            if i['subpart'] != "":
                data_by_tags[i['subpart']].append(preparing_data(i))

        with pd.ExcelWriter('data.xlsx', mode='w') as writer:
            for key in data_by_tags.keys():
                doc = pd.DataFrame.from_dict(data_by_tags[key])
                doc.to_excel(writer, sheet_name=key)
    else:
        data = []
        for i in items:
            data.append(preparing_data(i))
        doc = pd.DataFrame.from_dict(data)
        doc.to_excel("data.xlsx")

    with open("data.xlsx", "rb") as f:
        bot.send_document(message.chat.id, f, caption=f"Выкаченные объявления ({len(items)})")


if __name__ == "__main__":
    print("Start")
    bot.polling(none_stop=True, timeout=60)
