# -*- coding: utf-8 -*-
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import TelegramAPIError, BadRequest
import copy
import asyncio
import mysql.connector
import config
import pyowm
from pyowm.utils.config import get_default_config
from lxml import etree
from PIL import Image, ImageDraw, ImageFont
import os
import random
import datetime
import time
import pytz
from pytz import timezone
from datetime import date, datetime, timedelta
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import json
import pandas as pd

bot = Bot(token='token')
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class Change_weather_city(StatesGroup):
    id_message = State()

class Change_name(StatesGroup):
    id_message = State()

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await bot.delete_message(message.chat.id, message.message_id)
    keyboard = InlineKeyboardMarkup()
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    sql = '''SELECT readiness FROM users WHERE id = %s'''
    cursor.execute(sql, [message.chat.id])
    pred_status = cursor.fetchone()
    connection.close()
    if pred_status == None:
        keyboard.row(InlineKeyboardButton('🛠 Настроить', callback_data='Configure bot step 1'))
        await bot.send_photo(message.chat.id, open('Новостной бот 2.jpg', 'rb'), caption = config.welcome_message.format(message.chat.first_name), reply_markup = keyboard)
    else:
        keyboard.row(InlineKeyboardButton('🛠 Настроить', callback_data='Configure bot step 2 new'))
        if int(pred_status[0]) == 1:
            status = await finish_setting_status(message.chat.id)
            rates, weather = await finish_setting_shaping(status)
            keyboard.row(InlineKeyboardButton('🛑 Отписаться от рассылки', callback_data='Cancel subscription'))
            await bot.send_photo(message.chat.id, open('Новостной бот 2.jpg', 'rb'), caption = config.start_setting.format(status[0], status[1], rates, weather, config.state[int(status[6])], config.state[int(status[7])], config.state[int(status[8])]), reply_markup = keyboard)
        if int(pred_status[0]) == 0:
            await bot.send_photo(message.chat.id, open('Новостной бот 2.jpg', 'rb'), caption = config.cancel_subscription_2, reply_markup = keyboard)

@dp.callback_query_handler(lambda call: call.data == 'Cancel subscription')
async def cancel_subscription(call):
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    sql = '''UPDATE users SET readiness = %s WHERE id = %s'''
    cursor.execute(sql, (0, call.message.chat.id))
    connection.commit()
    connection.close()
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton('🛠 Настроить', callback_data='Configure bot step 2 new'))
    await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.cancel_subscription, reply_markup = keyboard)

async def clock_keyboard(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.row_width = 6
    for i in range(4):
        all_buttons = []
        keyboard.row(InlineKeyboardButton(config.times_of_day[i], callback_data='pass'))
        for j in range(6):
            all_buttons.append(InlineKeyboardButton(str(j+6*i)+':00', callback_data=j+6*i))
        keyboard.row(all_buttons[0], all_buttons[1], all_buttons[2], all_buttons[3], all_buttons[4], all_buttons[5])
    if call == 'Change hour':
        keyboard.row(InlineKeyboardButton('🔙 Назад', callback_data='Additional settings'))
    return keyboard

@dp.callback_query_handler(lambda call: call.data == 'Configure bot step 1')
async def сonfigure_bot_step_1(call):
    await bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media = InputMediaPhoto(open('Выбор времени.jpg', 'rb')))
    await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.configure_bot_step_1, reply_markup = await clock_keyboard('Configure bot step 1'))

async def keyboard_shaping(user):
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    sql = '''SELECT exchange_rates, quote_of_the_day, movie_of_the_day, weather_city, city FROM users WHERE id = %s''' % (user)
    cursor.execute(sql)
    status = cursor.fetchone()
    connection.close()
    if status[len(config.parameters)] != None:
        city_name = f'Прогноз погоды - {status[len(config.parameters)]}'
    else:
        city_name = 'Прогноз погоды'
    decoding_parameters = copy.deepcopy(config.decoding_parameters)
    decoding_parameters.append(city_name)
    keyboard = InlineKeyboardMarkup()
    for i in range(len(config.parameters)):
        keyboard.row(InlineKeyboardButton(config.state[status[i]]+' '+decoding_parameters[i], callback_data=config.parameters[i]+' '+str(status[i])))
    keyboard.row(InlineKeyboardButton('➕ Дополнительные настройки', callback_data='Additional settings'))
    keyboard.row(InlineKeyboardButton('☑️ Закончить настройку', callback_data='Finish setting'))
    return keyboard

@dp.callback_query_handler(lambda call: call.data in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23'])
async def сonfigure_bot_time(call):
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    sql = '''SELECT EXISTS(SELECT id FROM users WHERE id = %s)''' % (call.message.chat.id)
    cursor.execute(sql)
    status = cursor.fetchone()[0]
    if status == 0:
        sql = '''INSERT INTO users (id, name, city, times_of_day, exchange_rates, weather_city, quote_of_the_day, movie_of_the_day, readiness, notifications, exchange_rates_comb) VALUES (%s, %s, DEFAULT, %s, DEFAULT, DEFAULT, DEFAULT, DEFAULT, DEFAULT, DEFAULT, DEFAULT)'''
        cursor.execute(sql, (call.message.chat.id, call.message.chat.first_name, int(call.data)))
        connection.commit()
        connection.close()
        await bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media = InputMediaPhoto(open('Новостной бот 3.jpg', 'rb')))
        await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.configure_bot_step_2.format(call.data), reply_markup = await keyboard_shaping(call.message.chat.id))
    else:
        sql = f'''UPDATE users SET times_of_day = %s WHERE id = %s'''
        cursor.execute(sql, (int(call.data), call.message.chat.id))
        connection.commit()
        connection.close()
        await bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media = InputMediaPhoto(open('Новостной бот 4.jpg', 'rb')))
        await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.additional_settings_change.format(call.data), reply_markup = await additional_settings_keyboard(call.message.chat.id))

@dp.callback_query_handler(lambda call: call.data == 'Configure bot step 2' or call.data == 'Configure bot step 2 new')
async def сonfigure_bot_step_2(call):
    if call.data == 'Configure bot step 2 new':
        connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
        cursor = connection.cursor()
        sql = '''UPDATE users SET readiness = %s WHERE id = %s'''
        cursor.execute(sql, (0, call.message.chat.id))
        connection.commit()
        connection.close()
    await bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media = InputMediaPhoto(open('Новостной бот 3.jpg', 'rb')))
    await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.configure_bot_step_2_continue, reply_markup = await keyboard_shaping(call.message.chat.id))

@dp.callback_query_handler(lambda call: call.data == 'exchange_rates 0' or call.data == 'exchange_rates 1' or call.data == 'quote_of_the_day 0' or call.data == 'quote_of_the_day 1' or call.data == 'movie_of_the_day 0' or call.data == 'movie_of_the_day 1' or call.data == 'notifications 0' or call.data == 'notifications 1' or call.data == 'weather_city 0' or call.data == 'weather_city 1')
async def all_sections(call):
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    sql = f'''UPDATE users SET {call.data.split()[0]} = %s WHERE id = %s'''
    cursor.execute(sql, (config.values[int(call.data.split()[1])], call.message.chat.id))
    connection.commit()
    connection.close()
    if call.data == 'notifications 0' or call.data == 'notifications 1':
        await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.additional_settings, reply_markup = await additional_settings_keyboard(call.message.chat.id))
    elif call.data == 'exchange_rates 0' or call.data == 'exchange_rates 1':
        txt, keyboard = await exchange_rates_keyboard(call.message.chat.id)
        await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = txt, reply_markup = keyboard)
    elif call.data == 'weather_city 0' or call.data == 'weather_city 1':
        await bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media = InputMediaPhoto(open('Новостной бот 3.jpg', 'rb')))
        await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.configure_bot_step_2_continue, reply_markup = await keyboard_shaping(call.message.chat.id))
    else:
        await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.configure_bot_step_2_continue, reply_markup = await keyboard_shaping(call.message.chat.id))

async def additional_settings_keyboard(user):
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    sql = '''SELECT notifications FROM users WHERE id = %s''' % (user)
    cursor.execute(sql)
    status = cursor.fetchone()
    connection.close()
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton('🔄 Изменить имя', callback_data='Change name'))
    keyboard.row(InlineKeyboardButton('🔄 Изменить время', callback_data='Change hour'))
    keyboard.row(InlineKeyboardButton(f'{config.state[status[0]]} Уведомления', callback_data=f'notifications {status[0]}'))
    keyboard.row(InlineKeyboardButton('🔙 Назад', callback_data='Configure bot step 2'))
    return keyboard

@dp.callback_query_handler(lambda call: call.data == 'Additional settings')
async def additional_settings(call):
    await bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media = InputMediaPhoto(open('Новостной бот 4.jpg', 'rb')))
    await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.additional_settings, reply_markup = await additional_settings_keyboard(call.message.chat.id))

async def сonfigure_bot_weather_city_keyboard(user):
    keyboard = InlineKeyboardMarkup()
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    sql = '''SELECT weather_city, city FROM users WHERE id = %s''' % (user)
    cursor.execute(sql)
    status = cursor.fetchone()
    connection.close()
    if int(status[0]) == 0:
        if status[1] == None:
            txt = config.weather_city_new
            keyboard.row(InlineKeyboardButton('🆕 Добавить город', callback_data='weather_city change'))
        else:
            txt = config.weather_city_old_off
            keyboard.row(InlineKeyboardButton('❌ Информирование о погоде', callback_data='weather_city 0'))
            keyboard.row(InlineKeyboardButton('🔄 Сменить город', callback_data='weather_city change'))
    else:
        txt = config.weather_city_old_on
        keyboard.row(InlineKeyboardButton('✅ Информирование о погоде', callback_data='weather_city 1'))
        keyboard.row(InlineKeyboardButton('🔄 Сменить город', callback_data='weather_city change'))
    keyboard.row(InlineKeyboardButton('🔙 Назад', callback_data='Configure bot step 2'))
    return txt, keyboard

async def get_weather_information(city):
    config_dict = get_default_config()
    config_dict['language'] = 'ru'
    owm = pyowm.OWM(config.owm_api, config_dict)
    mgr = owm.weather_manager()
    observation = mgr.weather_at_place(city)
    w = observation.weather
    temperature = round(w.temperature('celsius')['temp'])
    wind_speed = round(w.wind()['speed'])
    wind_direction = w.wind()['deg']
    pressure = round(w.pressure['press']*100/133.32)
    humidity = w.humidity
    detailed_status = w.detailed_status
    return temperature, wind_speed, wind_direction, pressure, humidity, detailed_status

@dp.callback_query_handler(lambda call: call.data == 'weather_city_all 0' or call.data == 'weather_city_all 1')
async def сonfigure_bot_weather_city_all(call):
    txt, keyboard = await сonfigure_bot_weather_city_keyboard(call.message.chat.id)
    await bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media = InputMediaPhoto(open('Новостной бот 1.jpg', 'rb')))
    await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = txt, reply_markup = keyboard)

@dp.callback_query_handler(lambda call: call.data == 'weather_city change')
async def сonfigure_bot_weather_city_change(call, state: FSMContext):
    await Change_weather_city.id_message.set()
    m = await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.weather_city_change)
    await state.update_data(id_message=m.message_id)

@dp.message_handler(state=Change_weather_city.id_message)
async def сonfigure_bot_weather_city_change_answer(message: types.Message, state: FSMContext):
    await bot.delete_message(message.chat.id, message.message_id)
    data = await state.get_data()
    cl = data.get('id_message')
    if message.text == '/cancel':
        await state.finish()
        txt, keyboard = await сonfigure_bot_weather_city_keyboard(message.chat.id)
        await bot.edit_message_caption(chat_id=message.chat.id, message_id=cl, caption = txt, reply_markup = keyboard)
    else:
        config_dict = get_default_config()
        config_dict['language'] = 'ru'
        owm = pyowm.OWM(config.owm_api, config_dict)
        mgr = owm.weather_manager()
        try:
            observation = mgr.weather_at_place(message.text)
            await state.finish()
            connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
            cursor = connection.cursor()
            sql = '''UPDATE users SET city = %s, weather_city = %s WHERE id = %s'''
            cursor.execute(sql, (message.text.capitalize(), 1, message.chat.id))
            sql1 = f'''SELECT * FROM weather WHERE city = %s'''
            cursor.execute(sql1, [message.text])
            status = cursor.fetchall()
            if len(status) == 0:
                temperature, wind_speed, wind_direction, pressure, humidity, detailed_status = await get_weather_information(message.text)
                sql2 = '''INSERT INTO weather (city, temperature, wind_speed, wind_direction, pressure, humidity, detailed_status) VALUES (%s, %s, %s, %s, %s, %s, %s)'''
                cursor.execute(sql2, (message.text, temperature, wind_speed, wind_direction, pressure, humidity, detailed_status))
            connection.commit()
            connection.close()
            await bot.edit_message_media(chat_id=message.chat.id, message_id=cl, media = InputMediaPhoto(open('Новостной бот 3.jpg', 'rb')))
            await bot.edit_message_caption(chat_id=message.chat.id, message_id=cl, caption = config.configure_bot_step_2_continue, reply_markup = await keyboard_shaping(message.chat.id))
        except:
            await Change_weather_city.id_message.set()
            await bot.edit_message_caption(chat_id=message.chat.id, message_id=cl, caption = config.weather_city_void)

@dp.callback_query_handler(lambda call: call.data == 'Change hour')
async def change_hour(call):
    await bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media = InputMediaPhoto(open('Выбор времени.jpg', 'rb')))
    await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.change_hour, reply_markup = await clock_keyboard('Change hour'))

async def exchange_rates_keyboard(user):
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    sql = '''SELECT exchange_rates, exchange_rates_comb FROM users WHERE id = %s''' % (user)
    cursor.execute(sql)
    status = cursor.fetchone()
    connection.close()
    keyboard = InlineKeyboardMarkup()
    for i in range(len(config.currencies)):
        keyboard.row(InlineKeyboardButton(config.state[int(status[1][i])]+' '+config.currencies[i], callback_data=config.currencies_parameters[i]+' '+str(status[1][i])))
    if int(status[0]) == 0:
        txt = config.currencies_text_off
        keyboard.row(InlineKeyboardButton('❌ Информирование о курсах', callback_data='exchange_rates 0'))
    else:
        txt = config.currencies_text_on
        keyboard.row(InlineKeyboardButton('✅ Информирование о курсах', callback_data='exchange_rates 1'))
    keyboard.row(InlineKeyboardButton('🔙 Назад', callback_data='Configure bot step 2'))
    return txt, keyboard

@dp.callback_query_handler(lambda call: call.data == 'exchange_rates_all 0' or call.data == 'exchange_rates_all 1')
async def exchange_rates_all(call):
    txt, keyboard = await exchange_rates_keyboard(call.message.chat.id)
    await bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media = InputMediaPhoto(open('Новостной бот 5.jpg', 'rb')))
    await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = txt, reply_markup = keyboard)

@dp.callback_query_handler(lambda call: call.data == 'Доллар_США 0' or call.data == 'Доллар_США 1' or call.data == 'Евро 0' or call.data == 'Евро 1' or call.data == 'Фунт_стерлингов 0' or call.data == 'Фунт_стерлингов 1' or call.data == 'Швейцарский_франк 0' or call.data == 'Швейцарский_франк 1' or call.data == 'Китайский_юань 0' or call.data == 'Китайский_юань 1' or call.data == 'Японская_иена 0' or call.data == 'Японская_иена 1')
async def exchange_rates_switch(call):
    place = config.currencies_parameters.index(call.data.split()[0])
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    sql = '''SELECT exchange_rates_comb FROM users WHERE id = %s''' % (call.message.chat.id)
    cursor.execute(sql)
    status = cursor.fetchone()[0]
    line_list = list(status)
    line_list[place] = config.values[int(call.data.split()[1])]
    line = ''.join(str(e) for e in line_list)
    if int(call.data.split()[1]) == 0:
        sql1 = f'''UPDATE users SET exchange_rates_comb = %s, exchange_rates = %s WHERE id = %s'''
        cursor.execute(sql1, (line, 1, call.message.chat.id))
    else:
        sql1 = f'''UPDATE users SET exchange_rates_comb = %s WHERE id = %s'''
        cursor.execute(sql1, (line, call.message.chat.id))
    connection.commit()
    connection.close()
    txt, keyboard = await exchange_rates_keyboard(call.message.chat.id)
    await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = txt, reply_markup = keyboard)

async def make_picture(user):
    color = (255, 255, 255)
    size_image = width_image, height_image = 807, 361
    img = Image.open('pic.jpg')
    font_path = 'Quinoa-Bold.ttf'
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, size=72)
    k = 2
    while True:
        width_text, height_text = draw.textsize(user, font)
        if width_text > 560:
            font = ImageFont.truetype(font_path, size=72-k)
            k += 2
        else:
            break
    offset_x, offset_y = font.getoffset(user)
    width_text += offset_x
    height_text += offset_y
    top_left_x = width_image/2-width_text/2
    top_left_y = height_image/2-height_text/2
    xy = top_left_x-95, top_left_y+35
    draw.text(xy, user, font=font, fill=color)
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklnopqrstuvwxyz'
    pic_name = ''
    for i in range(16):
        pic_name += random.choice(chars)
    img.save(f'{pic_name}.jpg')
    return pic_name

async def get_name(user):
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    sql = '''SELECT name FROM users WHERE id = %s''' % (user)
    cursor.execute(sql)
    status = cursor.fetchone()[0]
    connection.close()
    return status

async def change_name_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton('🔄 Изменить имя', callback_data='Change name continue'))
    keyboard.row(InlineKeyboardButton('🔙 Назад', callback_data='Additional settings'))
    return keyboard

@dp.callback_query_handler(lambda call: call.data == 'Change name')
async def change_name(call):
    status = await get_name(call.message.chat.id)
    pic_name = await make_picture(status)
    await bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media = InputMediaPhoto(open(f'{pic_name}.jpg', 'rb')))
    await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.change_name_start, reply_markup = await change_name_keyboard())
    os.remove(f'{pic_name}.jpg')

@dp.callback_query_handler(lambda call: call.data == 'Change name continue')
async def change_name_continue(call, state: FSMContext):
    await Change_name.id_message.set()
    await bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media = InputMediaPhoto(open('Новостной бот 7.jpg', 'rb')))
    m = await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.change_name_continue.format(call.message.chat.first_name))
    await state.update_data(id_message=m.message_id)

@dp.message_handler(state=Change_name.id_message)
async def change_name_answer(message: types.Message, state: FSMContext):
    await bot.delete_message(message.chat.id, message.message_id)
    data = await state.get_data()
    cl = data.get('id_message')
    await state.finish()
    if message.text != '/cancel':
        if message.text == '/setname':
            text = message.chat.first_name
        else:
            text = message.text
        connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
        cursor = connection.cursor()
        sql = f'''UPDATE users SET name = %s WHERE id = %s'''
        cursor.execute(sql, (text, message.chat.id))
        connection.commit()
        connection.close()
    status = await get_name(message.chat.id)
    pic_name = await make_picture(status)
    await bot.edit_message_media(chat_id=message.chat.id, message_id=cl, media = InputMediaPhoto(open(f'{pic_name}.jpg', 'rb')))
    await bot.edit_message_caption(chat_id=message.chat.id, message_id=cl, caption = config.change_name_start, reply_markup = await change_name_keyboard())
    os.remove(f'{pic_name}.jpg')

async def finish_setting_status(user):
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    sql = '''SELECT name, times_of_day, exchange_rates, exchange_rates_comb, weather_city, city, quote_of_the_day, movie_of_the_day, notifications FROM users WHERE id = %s''' % (user)
    cursor.execute(sql)
    status = cursor.fetchone()
    connection.close()
    return status

async def finish_setting_shaping(status):
    if int(status[2]) == 0:
        rates = config.state[0]
    else:
        rates = config.state[1]+' ('
        for i in range(len(config.currencies)):
            if status[3][i] == '1':
                rates += config.currencies[i]+', '
        rates += ')'
        rates = rates.replace(', )', ')')
    if int(status[4]) == 0:
        weather = config.state[0]
    else:
        weather = config.state[1]+f' ({status[5]})'
    return rates, weather

@dp.callback_query_handler(lambda call: call.data == 'Finish setting')
async def finish_setting(call):
    status = await finish_setting_status(call.message.chat.id)
    if status[2] == 0 and status[4] == 0 and status[6] == 0 and status[7] == 0:
        await bot.answer_callback_query(call.id, show_alert=True, text=config.finish_setting_error)
    else:
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton('❌ Удалить сообщение', callback_data='Delete message'))
        rates, weather = await finish_setting_shaping(status)
        connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
        cursor = connection.cursor()
        sql = '''UPDATE users SET readiness = %s WHERE id = %s'''
        cursor.execute(sql, (1, call.message.chat.id))
        connection.commit()
        connection.close()
        await bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media = InputMediaPhoto(open('Новостной бот 6.jpg', 'rb')))
        await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption = config.finish_setting.format(status[0], status[1], rates, weather, config.state[int(status[6])], config.state[int(status[7])], config.state[int(status[8])]), reply_markup = keyboard)

@dp.callback_query_handler(lambda call: call.data == 'Delete message')
async def delete_message(call):
    try:
        await bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        await bot.answer_callback_query(call.id, show_alert=True, text=config.delete_message)

@dp.message_handler(content_types=['text', 'sticker', 'photo', 'audio', 'video', 'voice', 'location'])
async def send_text(message):
    await bot.delete_message(message.chat.id, message.message_id)

@dp.errors_handler(exception=TelegramAPIError)
async def telegram_API_error(update, error):
    return True

async def message_formation():
    exchange_rates = []
    ist = pytz.timezone('Europe/Moscow')
    now = datetime.now(tz=ist)
    hours = int(now.hour)+1
    if hours == 24:
        hours = 0
    if hours <= 5:
        hello = 'Доброй ночи'
    elif hours <= 11:
        hello = 'Доброе утро'
    elif hours <= 17:
        hello = 'Добрый день'
    else:
        hello = 'Добрый вечер'
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    cursor.execute('SET NAMES utf8mb4')
    sql = '''SELECT id, name, city, exchange_rates, exchange_rates_comb, weather_city, quote_of_the_day, movie_of_the_day, notifications FROM users WHERE readiness = %s AND times_of_day = %s''' % (1, hours)
    cursor.execute(sql)
    users = cursor.fetchall()
    sql1 = '''SELECT value FROM data WHERE field = %s'''
    cursor.execute(sql1, ['Цитата дня'])
    number = cursor.fetchone()
    sql2 = '''SELECT phrase, author FROM phrases WHERE id = %s'''
    cursor.execute(sql2, [int(number[0])])
    quote = cursor.fetchone()
    sql4 = '''SELECT value FROM data WHERE field = %s'''
    cursor.execute(sql4, ['Фильм дня'])
    film = cursor.fetchone()
    for i in range(len(config.currencies_parameters)):
        sql5 = '''SELECT value FROM data WHERE field = %s'''
        cursor.execute(sql5, [config.currencies_parameters[i]])
        course = cursor.fetchone()
        exchange_rates.append(round(float(course[0].replace(',', '.')), 2))
    connection.close()
    day = now.day
    month = now.month
    year = now.year
    if day < 10:
        day = f'0{day}'
    if month < 10:
        month = f'0{month}'
    for i in range(len(users)):
        connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database, use_unicode=True)
        cursor = connection.cursor()
        mess = config.send_message_1.format(hello, users[i][1])
        if int(users[i][5]) == 1:
            sql3 = '''SELECT city, temperature, wind_speed, wind_direction, pressure, humidity, detailed_status FROM weather WHERE city= %s'''
            cursor.execute(sql3, [users[i][2]])
            weather = cursor.fetchone()
            num = round(int(weather[3])/45)
            mess += config.send_message_2.format(weather[0], weather[6], weather[1], config.direction_of_the_wind[int(num)], weather[2], weather[4], weather[5])
        if int(users[i][6]) == 1:
            mess += config.send_message_3.format(quote[0], quote[1])
        if int(users[i][3]) == 1:
            mess += config.send_message_4
            for j in range(len(users[i][4])):
                if int(users[i][4][j]) == 1:
                    mess += f'\r\n{config.currencies[j]}: {exchange_rates[j]} руб.'
        if int(users[i][7]) == 1:
            mess += film[0]
        mess += config.send_message_6.format(day, month, year, hours)
        cursor.execute('SET NAMES utf8mb4')
        sql4 = '''INSERT INTO distribution (id, message, notifications) VALUES (%s, %s, %s)'''
        cursor.execute(sql4, (users[i][0], mess, users[i][8]))
        connection.commit()
        connection.close()

async def sending_messages():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton('❌ Удалить сообщение', callback_data='Delete message'))
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database, use_unicode=True)
    cursor = connection.cursor()
    cursor.execute('SET NAMES utf8mb4')
    sql = '''SELECT id, message, notifications FROM distribution'''
    cursor.execute(sql)
    users = cursor.fetchall()
    sql1 = '''DELETE FROM distribution'''
    cursor.execute(sql1)
    connection.commit()
    connection.close()
    for i in range(len(users)):
        if int(users[i][2]) == 1:
            notif = False
        else:
            notif = True
        await bot.send_message(chat_id = users[i][0], text = users[i][1], reply_markup = keyboard, disable_notification = notif, disable_web_page_preview = True, parse_mode = 'HTML')

async def at_minute_start():
    while True:
        now = datetime.now()
        after_minute = now.minute*60 + now.second + now.microsecond/1_000_000
        if after_minute:
            await asyncio.sleep(3300 - after_minute)
            await message_formation()
            now = datetime.now()
            after_minute = now.minute*60 + now.second + now.microsecond/1_000_000
            await asyncio.sleep(3600 - after_minute)
            await sending_messages()

async def req(url):
    UserAgent().chrome
    r = requests.get(url, headers={'User-Agent': UserAgent().chrome})
    r.encoding = 'utf8'
    return r.text

async def getFilm(html):
    soup = BeautifulSoup(html, 'lxml')
    filmName = soup.find('p', class_="selection-film-item-meta__name").string
    country = soup.find('p', class_="selection-film-item-meta__meta-additional").contents[0]
    genre = soup.find('p', class_="selection-film-item-meta__meta-additional").contents[1]
    rating = soup.find('span', class_="rating__value rating__value_positive")
    movieUrl = soup.find(class_='selection-film-item-meta__link').get('href')
    movieUrl = 'https://www.kinopoisk.ru' + movieUrl
    movieHTML = await req(movieUrl)
    returnCortage = [filmName.string, country.string, genre.string, rating.string, movieHTML, movieUrl]
    return returnCortage

async def getDiscription(movieHTML):
    soup = BeautifulSoup(movieHTML, 'lxml')
    description = soup.find('p', class_="styles_paragraph__2Otvx")
    return description.text

async def data_retrieval():
    ist = pytz.timezone('Europe/Moscow')
    now = datetime.now(tz=ist)
    day = now.day
    month = now.month
    year = now.year
    if day < 10:
        day = f'0{day}'
    if month < 10:
        month = f'0{month}'
    tree = etree.parse(f'http://www.cbr.ru/scripts/XML_daily.asp?date_req={day}/{month}/{year}')
    root = tree.getroot()
    mass = []
    mass.append(root[10][4].text)
    mass.append(root[11][4].text)
    mass.append(root[2][4].text)
    mass.append(root[30][4].text)
    mass.append(root[16][4].text)
    mass.append(root[33][4].text)
    num = random.randint(1,100)
    url = 'https://www.kinopoisk.ru/popular/films/?is-redirected=1'
    cortage = await getFilm(await req(url))
    description = await getDiscription(cortage[4])
    film_description = config.send_message_5.format(cortage[5], cortage[0], cortage[1], cortage[2], cortage[3], description)
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    cursor.execute('SET NAMES utf8mb4')
    for i in range(len(config.currencies_parameters)):
        sql = '''UPDATE data SET value = %s WHERE field = %s'''
        cursor.execute(sql, (mass[i], config.currencies_parameters[i]))
    sql1 = '''UPDATE data SET value = %s WHERE field = %s'''
    cursor.execute(sql1, (str(num), 'Цитата дня'))
    sql2 = '''UPDATE data SET value = %s WHERE field = %s'''
    cursor.execute(sql2, (film_description, 'Фильм дня'))
    connection.commit()
    connection.close()

async def at_minute_start_2():
    await data_retrieval()
    while True:
        ist = pytz.timezone('Europe/Moscow')
        now = datetime.now(tz=ist)
        after_minute = now.hour*3600 + now.minute*60 + now.second + now.microsecond/1_000_000
        if after_minute:
            await asyncio.sleep(86400 - after_minute)
            await data_retrieval()

async def weather_update():
    connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
    cursor = connection.cursor()
    sql = '''SELECT city FROM weather'''
    cursor.execute(sql)
    city = cursor.fetchall()
    connection.close()
    for i in range(len(city)):
        temperature, wind_speed, wind_direction, pressure, humidity, detailed_status = await get_weather_information(city[i][0])
        connection = mysql.connector.connect(user=config.user, password=config.password, host=config.host, port=config.port, database=config.database)
        cursor = connection.cursor()
        sql1 = '''UPDATE weather SET temperature = %s, wind_speed = %s, wind_direction = %s, pressure = %s, humidity = %s, detailed_status = %s WHERE city = %s'''
        cursor.execute(sql1, (temperature, wind_speed, wind_direction, pressure, humidity, detailed_status, city[i][0]))
        connection.commit()
        connection.close()

DELAY = 3600

def repeat(coro, loop):
    asyncio.ensure_future(coro(), loop=loop)
    loop.call_later(DELAY, repeat, coro, loop)

loop = asyncio.get_event_loop()
loop.create_task(at_minute_start())
loop.create_task(at_minute_start_2())
loop.call_later(DELAY, repeat, weather_update, loop)
executor.start_polling(dp, loop=loop)
loop.run_forever()
