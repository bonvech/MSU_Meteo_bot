from datetime import datetime, timedelta
import json
import os
import re
import telebot
from telebot import types
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px

bot = telebot.TeleBot('6727673127:AAFG9CY-YrV1_Y77duF50_JiKlJae29HCKs')
list_devices = os.listdir('data')


def load_json(path):
    return json.load(open(path, 'r'))


def upload_json(path, to_save):
    with open(path, 'w') as outfile:
        json.dump(to_save, outfile)


@bot.message_handler(commands=['preprocessing_all_files'])
def preprocessing_all_files(message):
    for path in list_devices:
        for file in os.listdir(f'data/{path}'):
            if file.endswith('.csv'):
                preprocessing_one_file(f'data/{path}/{file}')


def preprocessing_one_file(path):
    _, device, file_name = path.split('/')
    df = pd.read_csv(path, sep=None, engine='python')

    time_col = load_json('config_devices.json')[device]['time_cols']
    if device == "AE33-S09-01249":
        df[time_col] = pd.to_datetime(df[time_col], format="%d.%m.%Y %H:%M")
    if device == "LVS" or device == "PNS":
        col = list(df.columns)
        df = df.drop('Error', axis=1)
        col.remove("Time")
        df.columns = col
        df[time_col] = pd.to_datetime(df[time_col], format="%d.%m.%Y %H:%M:%S")
    if device == "TCA08":
        df[time_col] = pd.to_datetime(df[time_col], format="%Y-%m-%d %H:%M:%S")
    if device == "Web_MEM":
        df[time_col] = pd.to_datetime(df[time_col], format="%d.%m.%Y %H:%M")
    cols_to_draw = load_json('config_devices.json')[device]['cols']
    time_col = load_json('config_devices.json')[device]['time_cols']
    df = df[cols_to_draw + [time_col]]
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
    """df.set_index(time_col, inplace=True)
    df = df.replace(',', '.', regex=True).astype(float)
    df.reset_index(inplace=True)"""
    name = re.split("[-_]", file_name)
    if not os.path.exists(f'proc_data/{device}'):
        os.makedirs(f'proc_data/{device}')
    df.to_csv(f'proc_data/{device}/{name[0]}_{name[1]}.csv')
    return f'proc_data/{device}/{name[0]}_{name[1]}.csv'


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Просмотр данных с приборов"))
    bot.send_message(message.chat.id,
                     text=f"Здравствуйте, коллега. Этот бот создан для просмотра данных с этих приборов: "
                          f"{', '.join(list_devices)}",
                     reply_markup=markup)


def work_with_latest_file(user_id):
    user_info_open = load_json('user_info.json')
    device = user_info_open[user_id]['device']
    last_record_file = f"data/{device}/{max(list(filter(lambda x: '.csv' in x, os.listdir(f'data/{device}'))))}"
    file_name = pd.read_csv(preprocessing_one_file(last_record_file))
    max_date = str(file_name[load_json('config_devices.json')[device]['time_cols']].max()).split()[0]
    devices_tech_info_open = load_json('devices_tech_info.json')
    devices_tech_info_open[device] = {'last_record_file': last_record_file}
    user_info_open[user_id]['last_record_date'] = max_date
    upload_json('user_info.json', user_info_open)
    upload_json('devices_tech_info.json', devices_tech_info_open)


def work_with_first_file(user_id):
    device = load_json('user_info.json')[user_id]['device']
    first_record_file = min(list(filter(lambda x: '.csv' in x, os.listdir(f'proc_data/{device}'))))
    df = pd.read_csv(f"proc_data/{device}/{first_record_file}")
    time_col = load_json('config_devices.json')[device]['time_cols']
    devices_tech_info_open = load_json('devices_tech_info.json')
    devices_tech_info_open[device]['first_record_date'] = str(df[time_col].min()).split()[0]
    upload_json('devices_tech_info.json', devices_tech_info_open)


@bot.message_handler(func=lambda message: message.text == 'Просмотр данных с приборов' or message.text in list_devices)
def choose_device(message):
    if message.text == 'Просмотр данных с приборов':
        markup = types.ReplyKeyboardMarkup(row_width=1)
        markup.add(*list(map(lambda x: types.KeyboardButton(x), list_devices)))
        bot.send_message(message.chat.id, "Выберите прибор", reply_markup=markup)

    elif message.text in list_devices:
        user_info_open = load_json('user_info.json')
        user_info_open[str(message.from_user.id)] = {'device': message.text}
        upload_json('user_info.json', user_info_open)
        work_with_latest_file(str(message.from_user.id))
        work_with_first_file(str(message.from_user.id))
        choose_time_delay(message)


@bot.message_handler(func=lambda message: message.text in ['2 дня', '7 дней', '14 дней',
                                                           '31 день'] or message.text == 'Свой временной промежуток')
def choose_time_delay(message):
    if message.text in ['2 дня', '7 дней', '14 дней', '31 день']:
        delay = 2 if message.text == '2 дня' else 7 if message.text == '7 дней' else 14 if message.text == '14 дней' else 31
        user_info_open = load_json('user_info.json')
        end_record_date = user_info_open[str(message.from_user.id)]['last_record_date']
        begin_record_date = (datetime.strptime(end_record_date, '%Y-%m-%d') - timedelta(days=delay)).strftime(
            '%Y-%m-%d')
        user_info_open[str(message.from_user.id)]['begin_record_date'] = str(begin_record_date).split()[0]
        upload_json('user_info.json', user_info_open)
        # choose_columns(message)
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
    devices_tech_info_open = load_json('devices_tech_info.json')
    device = load_json('user_info.json')[str(message.from_user.id)]['device']
    first_record_date = devices_tech_info_open[device]['first_record_date']
    first_record_date = datetime.strptime(first_record_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    last_record_date = devices_tech_info_open[device]['last_record_date']
    last_record_date = datetime.strptime(last_record_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    bot.send_message(message.chat.id, f"Данные досупны с {first_record_date} по {last_record_date}")
    msg = bot.send_message(message.chat.id, "Дата начала отрезка данных (в формате 'день.месяц.год')",
                           reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, begin_record_date_choose)


def begin_record_date_choose(message):
    devices_tech_info_open = load_json('devices_tech_info.json')
    user_info_open = load_json('user_info.json')
    device = user_info_open[str(message.from_user.id)]['device']
    first_record_date = devices_tech_info_open[device]['first_record_date']
    first_record_date = datetime.strptime(first_record_date, "%Y-%m-%d").date()
    last_record_date = devices_tech_info_open[device]['last_record_date']
    last_record_date = datetime.strptime(last_record_date, "%Y-%m-%d").date()
    try:
        begin_record_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        if not last_record_date >= begin_record_date >= first_record_date:
            raise ValueError
        user_info_open[str(message.from_user.id)]['begin_record_date'] = str(begin_record_date).split()[0]
        upload_json('user_info.json', user_info_open)
        choose_not_default_finish_date(message)
    except ValueError:
        bot.send_message(message.chat.id, "Введенане корректная дата")
        choose_not_default_start_date(message)


def choose_not_default_finish_date(message):
    msg = bot.send_message(message.chat.id, "Дата конца отрезка данных (в формате 'день.месяц.год')")
    bot.register_next_step_handler(msg, end_record_date_choose)


def end_record_date_choose(message):
    devices_tech_info_open = load_json('devices_tech_info.json')
    user_info_open = load_json('user_info.json')
    device = user_info_open[str(message.from_user.id)]['device']
    begin_record_date = user_info_open[str(message.from_user.id)]['begin_record_date']
    begin_record_date = datetime.strptime(begin_record_date, "%Y-%m-%d").date()
    last_record_date = devices_tech_info_open[device]['last_record_date']
    last_record_date = datetime.strptime(last_record_date, "%Y-%m-%d").date()

    try:
        end_record_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        if not (last_record_date >= end_record_date >= begin_record_date):
            raise ValueError
        user_info_open[str(message.from_user.id)]['last_record_date'] = str(end_record_date).split()[0]
        upload_json('user_info.json', user_info_open)
        concat_files(message)
        # choose_columns(message)
    except ValueError:
        bot.send_message(message.chat.id, "Введена некорректная дата")
        choose_not_default_finish_date(message)


def concat_files(message):
    user_info_open = load_json('user_info.json')
    user_id = user_info_open[str(message.from_user.id)]
    device = user_id['device']
    begin_record_date = datetime.strptime(user_id['begin_record_date'], '%Y-%m-%d')
    end_record_date = datetime.strptime(user_id['last_record_date'], '%Y-%m-%d')
    current_date, combined_data = begin_record_date, pd.DataFrame()
    while current_date <= end_record_date + timedelta(days=32):
        try:
            data = pd.read_csv(f"{device}/{current_date.strftime('%Y_%m')}_{device}.csv")
            combined_data = pd.concat([combined_data, data], ignore_index=True)
            current_date += timedelta(days=29)
        except FileNotFoundError:
            current_date += timedelta(days=31)
    begin_record_date = pd.to_datetime(begin_record_date)
    end_record_date = pd.to_datetime(end_record_date)
    time_col = load_json('config_devices.json')[device]['time_cols']
    combined_data[time_col] = pd.to_datetime(combined_data[time_col], format="%Y-%m-%d %H:%M:%S")
    combined_data = combined_data[
        (combined_data[time_col] >= begin_record_date) & (combined_data[time_col] <= end_record_date)]
    if (end_record_date - begin_record_date).days > 2 and len(combined_data) >= 500:
        combined_data = combined_data.resample('60min').mean()
    cols_to_draw = load_json('config_devices.json')[device]['cols']
    combined_data.set_index(time_col, inplace=True)
    combined_data = combined_data.replace(',', '.', regex=True).astype(float)
    combined_data.reset_index(inplace=True)
    fig = px.line(combined_data, x=time_col, y=cols_to_draw)
    fig.write_image(f"graphs_photo/{str(message.from_user.id)}.png")
    bot.send_photo(str(message.from_user.id), photo=open(f"graphs_photo/{str(message.from_user.id)}.png", 'rb'))
    plt.close()


bot.polling(none_stop=True)

"""
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
"""

"""def choose_columns(message):
    user_info_open = json.load(open('user_info.json', 'r'))
    markup = types.InlineKeyboardMarkup(row_width=1)
    device = user_info_open[str(message.from_user.id)]['device']
    ava_col = json.load(open('config_devices.json', 'r'))[device]['cols']
    for i in ava_col:
        markup.add(types.InlineKeyboardButton(str(i), callback_data=str(i)))
    next = types.InlineKeyboardButton('Выбрано', callback_data='next')
    back = types.InlineKeyboardButton('Обратно', callback_data='back')
    markup.add(next, back)
    bot.send_message(message.chat.id, 'Столбцы для выбора:', reply_markup=markup)
"""
