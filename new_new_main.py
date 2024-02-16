import telebot
import requests
from telebot import types
import json
import os
import pandas as pd
from datetime import datetime, timedelta
import re
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.offline as offline



def files_in_folder(url, typ='all'):
    out = []
    parts = url.split("/")
    api_url = f"https://api.github.com/repos/{parts[3]}/{parts[4]}/contents/{'/'.join(parts[7:])}?ref={parts[6]}"
    data = requests.get(api_url).json()
    for item in data:
        if item['type'] == typ or typ == 'all':
            out.append(item['name'])
    return out


LIST_DEVICES = files_in_folder('https://github.com/omixyy/meteosite/tree/main/data', 'dir')
bot = telebot.TeleBot('6727673127:AAFG9CY-YrV1_Y77duF50_JiKlJae29HCKs')


@bot.message_handler(commands=['download_all'])
def download_all(message):
    for i in LIST_DEVICES:
        if not os.path.exists(f"{i}"):
            os.makedirs(f"{i}")
        list_files = list(
            filter(lambda x: '.csv' in x, files_in_folder(f"https://github.com/omixyy/meteosite/tree/main/data/{i}")))
        for j in list_files:
            link = f"https://github.com/omixyy/meteosite/tree/main/data/{i}/{j}"
            response = requests.get(format_github_link(link))
            name = re.split("-|_", j)
            with open(f"{i}/{name[0]}_{name[1]}_{i}.csv", "wb") as file:
                file.write(response.content)
            preprocessing_file(i, f"{i}/{name[0]}_{name[1]}_{i}.csv")


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Просмотр данных с приборов"))
    bot.send_message(message.chat.id,
                     text=f"Здравствуйте, коллега. Этот бот создан для просмотра данных с этих приборов: {LIST_DEVICES}",
                     reply_markup=markup)


def format_github_link(link):
    return link.replace('github.com', 'raw.githubusercontent.com').replace('/blob', '').replace('/tree', '')


def preprocessing_file(device, path):
    df = pd.read_csv(path, sep=None, engine='python')
    time_col = json.load(open('config_devices.json', 'r'))[device]['time_cols']
    if device == "AE33-S09-01249":
        df[time_col] = pd.to_datetime(df[time_col], format="%d.%m.%Y %H:%M")
    if device == "LVS" or device == "PNS":
        col = list(df.columns)
        try:
            df = df.drop('Error', axis=1)
        except KeyError:
            pass
        try:
            col.remove("Time")
        except ValueError:
            pass
        df.columns = col
        df[time_col] = pd.to_datetime(df[time_col], format="%d.%m.%Y %H:%M:%S")
    if device == "TCA08":
        df[time_col] = pd.to_datetime(df[time_col], format="%Y-%m-%d %H:%M:%S")
    if device == "Web_MEM":
        df[time_col] = pd.to_datetime(df[time_col], format="%d.%m.%Y %H:%M")
    cols_to_draw = json.load(open('config_devices.json', 'r'))[device]['cols']
    time_col = json.load(open('config_devices.json', 'r'))[device]['time_cols']
    df = df[cols_to_draw + [time_col]]
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
    df.to_csv(path, index=False)


def save_data_file_to_folder(device, file_name):
    link = f"https://github.com/omixyy/meteosite/tree/main/data/{device}/{file_name}"
    response = requests.get(format_github_link(link))
    if not os.path.exists(f"{device}"):
        os.makedirs(f"{device}")
    name = re.split("-|_", file_name)
    name_last_record_file = f"{device}/{name[0]}_{name[1]}_{device}.csv"
    with open(name_last_record_file, "wb") as file:
        file.write(response.content)
    preprocessing_file(device, name_last_record_file)


def work_with_latest_file(ID):
    user_info_open = json.load(open('user_info.json', 'r'))
    device = user_info_open[ID]['device']
    name_files = files_in_folder(
        f"https://github.com/omixyy/meteosite/tree/main/data/{device}")
    last_record_file = max(list(filter(lambda x: '.csv' in x, name_files)))
    name = re.split("-|_", last_record_file)
    name_last_record_file = f"{device}/{name[0]}_{name[1]}_{device}.csv"
    devices_tech_info_open = json.load(open('devices_tech_info.json', 'r'))
    devices_tech_info_open[device] = {'last_record_file': name_last_record_file}
    with open('devices_tech_info.json', 'w') as outfile:
        json.dump(devices_tech_info_open, outfile)
    save_data_file_to_folder(device, last_record_file)
    df = pd.read_csv(name_last_record_file)
    time_col = json.load(open('config_devices.json', 'r'))[device]['time_cols']
    devices_tech_info_open = json.load(open('devices_tech_info.json', 'r'))
    devices_tech_info_open[device]['last_record_date'] = str(df[time_col].max()).split()[
        0]
    with open('devices_tech_info.json', 'w') as outfile:
        json.dump(devices_tech_info_open, outfile)


def work_with_first_file(ID):
    user_info_open = json.load(open('user_info.json', 'r'))
    filenames = next(os.walk(f"{user_info_open[ID]['device']}"), (None, None, []))[2]
    df = pd.read_csv(f"{user_info_open[ID]['device']}/{min(filenames)}")
    time_col = json.load(open('config_devices.json', 'r'))[user_info_open[ID]['device']]['time_cols']
    devices_tech_info_open = json.load(open('devices_tech_info.json', 'r'))
    devices_tech_info_open[user_info_open[ID]['device']]['first_record_date'] = str(df[time_col].min()).split()[
        0]
    with open('devices_tech_info.json', 'w') as outfile:
        json.dump(devices_tech_info_open, outfile)


@bot.message_handler(func=lambda message: message.text == 'Просмотр данных с приборов' or message.text in LIST_DEVICES)
def choose_device(message):
    if message.text == 'Просмотр данных с приборов':
        markup = types.ReplyKeyboardMarkup(row_width=1)
        markup.add(*list(map(lambda x: types.KeyboardButton(x), LIST_DEVICES)))
        bot.send_message(message.chat.id, "Выберите прибор", reply_markup=markup)

    elif message.text in LIST_DEVICES:
        user_info_open = json.load(open('user_info.json', 'r'))
        user_info_open[str(message.from_user.id)] = {'device': message.text}
        with open('user_info.json', 'w') as outfile:
            json.dump(user_info_open, outfile)
        work_with_latest_file(str(message.from_user.id))
        work_with_first_file(str(message.from_user.id))
        choose_time_delay(message)


@bot.message_handler(func=lambda message: message.text in ['2 дня', '7 дней', '14 дней',
                                                           '31 день'] or message.text == 'Свой временной промежуток')
def choose_time_delay(message):
    if message.text in ['2 дня', '7 дней', '14 дней', '31 день']:
        delay = 2 if message.text == '2 дня' else 7 if message.text == '7 дней' else 14 if message.text == '14 дней' else 31
        user_info_open = json.load(open('user_info.json', 'r'))
        end_record_date = \
            json.load(open('devices_tech_info.json', 'r'))[user_info_open[str(message.from_user.id)]['device']][
                'last_record_date']
        user_info_open[str(message.from_user.id)]['end_record_date'] = str(end_record_date)
        with open('user_info.json', 'w') as outfile:
            json.dump(user_info_open, outfile)
        user_info_open = json.load(open('user_info.json', 'r'))
        begin_record_date = (datetime.strptime(end_record_date, '%Y-%m-%d') - timedelta(days=delay)).strftime(
            '%Y-%m-%d')
        user_info_open[str(message.from_user.id)]['begin_record_date'] = str(begin_record_date).split()[0]
        with open('user_info.json', 'w') as outfile:
            json.dump(user_info_open, outfile)
        concat_files(message)
    elif message.text == 'Свой временной промежуток':
        choose_not_default_start_date(message)
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton('2 дня'), types.KeyboardButton('7 дней'))
        markup.add(types.KeyboardButton('14 дней'), types.KeyboardButton('31 день'))
        markup.add(types.KeyboardButton('Свой временной промежуток'))
        bot.send_message(message.chat.id, "Выберите временной промежуток", reply_markup=markup)


def choose_not_default_start_date(message):
    devices_tech_info_open = json.load(open('devices_tech_info.json', 'r'))
    user_info_open = json.load(open('user_info.json', 'r'))
    first_record_date = devices_tech_info_open[user_info_open[str(str(message.from_user.id))]['device']][
        'first_record_date']
    first_record_date = datetime.strptime(first_record_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    last_record_date = devices_tech_info_open[user_info_open[str(str(message.from_user.id))]['device']][
        'last_record_date']
    last_record_date = datetime.strptime(last_record_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    bot.send_message(message.chat.id, f"Данные досупны с {first_record_date} по {last_record_date}")
    msg = bot.send_message(message.chat.id, "Дата начала отрезка данных (в формате 'день.месяц.год')",
                           reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, begin_record_date_choose)


def begin_record_date_choose(message):
    devices_tech_info_open = json.load(open('devices_tech_info.json', 'r'))
    user_info_open = json.load(open('user_info.json', 'r'))
    first_record_date = devices_tech_info_open[user_info_open[str(str(message.from_user.id))]['device']][
        'first_record_date']
    first_record_date = datetime.strptime(first_record_date, "%Y-%m-%d").date()
    last_record_date = devices_tech_info_open[user_info_open[str(str(message.from_user.id))]['device']][
        'last_record_date']
    last_record_date = datetime.strptime(last_record_date, "%Y-%m-%d").date()
    try:
        begin_record_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        if not (last_record_date >= begin_record_date >= first_record_date):
            raise ValueError
        user_info_open = json.load(open('user_info.json', 'r'))
        user_info_open[str(message.from_user.id)]['begin_record_date'] = str(begin_record_date).split()[0]
        with open('user_info.json', 'w') as outfile:
            json.dump(user_info_open, outfile)
        choose_not_default_finish_date(message)

    except ValueError:
        bot.send_message(message.chat.id, "Введена не корректная дата")
        choose_not_default_start_date(message)


def choose_not_default_finish_date(message):
    msg = bot.send_message(message.chat.id, "Дата конца отрезка данных (в формате 'день.месяц.год')")
    bot.register_next_step_handler(msg, end_record_date_choose)


def end_record_date_choose(message):
    devices_tech_info_open = json.load(open('devices_tech_info.json', 'r'))
    user_info_open = json.load(open('user_info.json', 'r'))
    begin_record_date = user_info_open[str(message.from_user.id)]['begin_record_date']
    begin_record_date = datetime.strptime(begin_record_date, "%Y-%m-%d").date()
    last_record_date = devices_tech_info_open[user_info_open[str(str(message.from_user.id))]['device']][
        'last_record_date']
    last_record_date = datetime.strptime(last_record_date, "%Y-%m-%d").date()
    try:
        end_record_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        if not (last_record_date >= end_record_date >= begin_record_date):
            raise ValueError
        user_info_open = json.load(open('user_info.json', 'r'))
        user_info_open[str(message.from_user.id)]['end_record_date'] = str(end_record_date).split()[0]
        with open('user_info.json', 'w') as outfile:
            json.dump(user_info_open, outfile)
        concat_files(message)

    except ValueError:
        bot.send_message(message.chat.id, "Введена не корректная дата")
        choose_not_default_finish_date(message)


def concat_files(message):
    user_info_open = json.load(open('user_info.json', 'r'))
    begin_record_date = datetime.strptime(user_info_open[str(message.from_user.id)]['begin_record_date'], '%Y-%m-%d')
    end_record_date = datetime.strptime(user_info_open[str(message.from_user.id)]['end_record_date'], '%Y-%m-%d')
    current_date = begin_record_date
    combined_data = pd.DataFrame()
    device = user_info_open[str(message.from_user.id)]['device']
    while current_date <= end_record_date + timedelta(days=32):
        try:
            data = pd.read_csv(f"{device}/{current_date.strftime('%Y_%m')}_{device}.csv")
            combined_data = pd.concat([combined_data, data], ignore_index=True)
            current_date += timedelta(days=29)
        except FileNotFoundError:
            current_date += timedelta(days=31)
    begin_record_date = pd.to_datetime(begin_record_date)
    end_record_date = pd.to_datetime(end_record_date)
    time_col = json.load(open('config_devices.json', 'r'))[device]['time_cols']
    combined_data[time_col] = pd.to_datetime(combined_data[time_col], format="%Y-%m-%d %H:%M:%S")
    combined_data = combined_data[
        (combined_data[time_col] >= begin_record_date) & (combined_data[time_col] <= end_record_date)]
    combined_data.set_index(time_col, inplace=True)
    combined_data = combined_data.replace(',', '.', regex=True).astype(float)
    if (end_record_date - begin_record_date).days > 2 and len(combined_data) >= 500:
        combined_data = combined_data.resample('60min').mean()
    combined_data.reset_index(inplace=True)
    cols_to_draw = json.load(open('config_devices.json', 'r'))[device]['cols']
    fig = px.line(combined_data, x=time_col, y=cols_to_draw)
    fig.write_image(f"graphs_photo/{str(message.from_user.id)}.png")
    bot.send_photo(str(message.from_user.id), photo=open(f"graphs_photo/{str(message.from_user.id)}.png", 'rb'))
    plt.close()

def make_graph(device):
    combined_data = pd.DataFrame()
    for i in next(os.walk(f"{device}"), (None, None, []))[2]:
        data = pd.read_csv(f"{device}/{i}")
        combined_data = pd.concat([combined_data, data], ignore_index=True)
    time_col = json.load(open('config_devices.json', 'r'))[device]['time_cols']
    combined_data.set_index(time_col, inplace=True)
    combined_data = combined_data.replace(',', '.', regex=True).astype(float)
    combined_data.reset_index(inplace=True)
    m = pd.to_datetime(max(combined_data[time_col]))
    last_48_hours = [m.replace(day=(m.day - 2)), m]
    cols_to_draw = json.load(open('config_devices.json', 'r'))[device]['cols']
    fig = px.line(combined_data, x=time_col, y=cols_to_draw, range_x=last_48_hours)
    fig.update_layout(legend_itemclick='toggle')
    offline.plot(fig, filename=f'templates/graph_{device}.html', auto_open=False)



bot.polling(none_stop=True)
# TODO: ОБЪЕДИНИТЬ work_with_first_file work_with_latest_file
# TODO: ОБТИМИЗИРОВАТЬ ВЫГРУЗКУ JSON, ЗАГРУЗКУ ДАННЫХ В НИХ(СЛОВАРИ), ЗАГРУЗКА СЛОВАРЕЙ
# TODO: ОПТИМИЗИРОВАТЬ У ПРИБОРОВ ПОСТОЯННО НАЧАЛЬНАЯ ДАТА
# TODO: МОЖНО ПРОСЧИТЫВАТЬ ПОСЛЕДНЮЮ ЗАПИСЬ ПО ДРГУОМУ, НАПРИМЕР ПО ДЕФОЛТУ СТАВИТЬ СЕГОДНЯШНЮЮ ДАТУ И подумать...
# TODO: ВВЕСТИ ОДИН ФОРМАТ ДАТ
# TODO: ОПТИМИЗИРОВАТЬ, ЧТО ФАЙЛЫ С НЕ ТЕКУЩИМ МЕСЯЦЕМ НЕ ОБНОВЛЯЮТСЯ И ИХ МОЖНО СКАЧИВАТЬ СНОВА И СНОВА, то есть
# TODO: продолжение старые скачать 1 раз, текущий скачивать каждый раз

# TODO: Прямо при загрузке данных надо удалять не нудные столбцы строчные)
# TODO: при стартовой дате TCA выдает ошибку