from srch import *
from datetime import datetime
import telebot
from telebot import types
from srch import *
from datetime import datetime

bot = telebot.TeleBot(TELEGRAM_TOKEN)
generate_button_text = "📝 Сгенерировать статью"
generate_button = types.KeyboardButton(generate_button_text)
markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
markup.add(generate_button)


@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(
        message.chat.id,
        "Привет! Я могу помочь сгенерировать статью и изображение к ней на основе новостей. \n"
        "Внизу появилась кнопка, жмите ее каждый раз, когда вам будет нужна новая статья",
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text == generate_button_text:
        bot.send_message(
            message.chat.id,
            "На какую тему нужно сгенерировать статью?",
        )
        bot.register_next_step_handler(message, generate_article)


def generate_article(message):
    text = message.text
    t_message = bot.send_message(
        message.chat.id, 'Бот обрабатывает сообщение')
    news = search_news(text)
    media = list()

    blog_text = generate_blog_text_mult_google(news, text)
    image_text = generate_image_text_google(blog_text, text)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    save_results(blog_text, image_text, timestamp)
    generate_Dif_image(image_text, timestamp)

    bot.delete_message(t_message.chat.id, t_message.message_id)
    image_path = f"results/images/dif_image_{timestamp}.png"
    blog_path = f"results/blog_text_{timestamp}.docx"
    prompt_path = f"results/image_prompt_{timestamp}.txt"

    # blog_a = types.InputMediaDocument(f"attach://{blog_path}")
    # prompt_a = types.InputMediaDocument(f"attach://{prompt_path}")
    # bot.send_media_group(message.chat.id, [blog_a, prompt_a])
    with open(image_path, 'rb') as photo:
        with open(prompt_path, 'rb') as prompt:
            with open(blog_path, mode='rb') as blog:
                bot.send_photo(message.chat.id, photo)
                bot.send_document(message.chat.id, document=prompt)
                bot.send_document(message.chat.id, document=blog)


if __name__ == '__main__':
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print('Error occurred:', str(e))
