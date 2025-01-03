import datetime
import os

import cohere
import requests
import torch
from bs4 import BeautifulSoup
from diffusers import BitsAndBytesConfig, SD3Transformer2DModel
from diffusers import StableDiffusion3Pipeline
from docx import Document
from newspaper import Article
from serpapi import GoogleSearch

from cfg import *

import pathlib
import textwrap

import google.generativeai as genai

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
co = cohere.Client(token)
model_id = "stabilityai/stable-diffusion-3.5-large"
genai.configure(api_key=google_api_token)
google_model = genai.GenerativeModel("gemini-2.0-flash-thinking-exp")

def search_news(q, loc="Russia", hl="ru", gl="ru", tbm=""):
    params = {
        "q": q,
        "location": loc,
        "hl": hl,
        "gl": gl,
        "api_key": serp_token,
        "tbm": tbm
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    key = [x for x in results.keys() if "results" in x]
    return results[key[0]][:5]  # Возвращаем 5 последних новостей


def get_article_text(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")

        # Попытка найти текст внутри распространенных контейнеров
        article_body = soup.find('article') or \
                       soup.find('div', class_='article-content') or \
                       soup.find('div', class_='content') or \
                       soup.find('div', class_='post-content')

        if article_body:
            paragraphs = article_body.find_all('p')  # Собираем абзацы только из основного блока
        else:
            # Если не найдено, возвращаем все параграфы на странице (может собрать лишнее)
            paragraphs = soup.find_all('p')

        article_text = " ".join([p.get_text() for p in paragraphs])
        return article_text.strip()
    except Exception as e:
        print(f"Не удалось получить текст с {url}: {e}")
        return ""


def get_article_text_v2(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text.strip()
    except Exception as e:
        print(f"Не удалось получить текст с {url}: {e}")
        return ""


def generate_blog_text_mult_cohere(news_items):
    collected_texts = []
    for item in news_items:
        article_url = item.get("link")
        if article_url:
            print(f"Скачиваем текст с {article_url}")
            # article_text = get_article_text(article_url)
            article_text = get_article_text_v2(article_url)
            if article_text:
                collected_texts.append(article_text)

    # Объединяем все собранные тексты в один
    combined_text = "\n".join(collected_texts)
    # Генерация текста блога с использованием собранных данных
    prompt = (f"Do not use memory.\nUsing the following news articles, write a brief,"
              f" engaging blog post aimed at mothers, discussing the importance of early childhood"
              f" education in arithmetic and speed reading. Keep the language simple, informative,"
              f" and engaging, focusing on how these skills benefit young children."
              f" Conclude the text in a logical, satisfying way. Do not overuse words. The output should"
              f" be in Russian.\n\nArticles: {combined_text}")
    response = co.generate(model="command-r-plus", prompt=prompt, max_tokens=1000)
    return response.generations[0].text.strip()


def generate_blog_text_mult_google(news_items, q):
    collected_texts = []
    for item in news_items:
        article_url = item.get("link")
        if article_url:
            print(f"Скачиваем текст с {article_url}")
            # article_text = get_article_text(article_url)
            article_text = get_article_text_v2(article_url)
            if article_text:
                collected_texts.append(article_text)

    # Объединяем все собранные тексты в один
    combined_text = "\n".join(collected_texts)
    # Генерация текста блога с использованием собранных данных
    prompt = (f"Do not use memory.\nUsing the following news articles, write a brief,"
              f" engaging blog post aimed at mothers, discussing the importance of early childhood"
              f" education in arithmetic and speed reading. Keep the language simple, informative,"
              f" and engaging, focusing on how these skills benefit young children."
              f" Conclude the text in a logical, satisfying way. Do not overuse words. The output should"
              f" be in Russian.\n\nArticles: {combined_text}")
    messages = [
        {"role": "user",
         "parts": ["Выступи в роли промпт-инженера, создай идеальный промпт для генерации логичного, логически "
                   "завершенного, полного, хорошо структурированного, понятного, интересного, захватывающего "
                   "текста для статьи, который бы не содержал излишнее количество перечислений и был бы информативен. "
                   "Твой выход должен содержать исключительно промпт без любых других объяснений. "
                   f"Тема статьи: '{q}'. После генерации промпта проверь себя на ошибки и исправь их, если найдешь"]}
    ]
    response = google_model.generate_content(messages)
    prompt = response.to_dict()['candidates'][-1]["content"]["parts"][-1]["text"] + ("\nТекст статьи должен быть "
                                                                                     f"построен на основе {combined_text}"
                                                                                     f", но в него можно добавлять "
                                                                                     f"что-то ещё. После генерации текста"
                                                                                     f"проверь себя на ошибки и исправь"
                                                                                     f"их, если нашёл таковые.")
    response = google_model.generate_content(prompt)
    return response.to_dict()['candidates'][-1]["content"]["parts"][-1]["text"]


def load_diffusion_model():
    nf4_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16
    )
    model_nf4 = SD3Transformer2DModel.from_pretrained(
        model_id,
        subfolder="transformer",
        quantization_config=nf4_config,
        torch_dtype=torch.bfloat16
    )

    pipeline = StableDiffusion3Pipeline.from_pretrained(
        model_id,
        transformer=model_nf4,
        torch_dtype=torch.bfloat16
    )
    pipeline.enable_model_cpu_offload()
    return pipeline


pipeline = load_diffusion_model()


def generate_image_text_cohere(blog_text):
    # prompt = (f"Generate a concise, effective, and creative prompt for Stable Diffusion in English based on the {blog_text}. Ensure your prompt is imaginative and accurately captures the essence of the text. Only the English prompt should be in the response.")
    prompt = (f'Based on the {blog_text}, create a prompt for Stable Diffusion to design a cover image that visually '
              f'captures main topic in the text. The image should be warm and inviting, with elements like young '
              f'children engaged in learning, friendly illustrations of numbers, or books. The scene should appeal '
              f'to mothers, conveying a nurturing and educational atmosphere, with soft colors and a joyful, '
              f'encouraging tone. The output should contain only the prompt without anything else. Max output length '
              f'is 77. Make sure to keep it logical in that length')
    response = co.generate(model="command-r-plus-04-2024", prompt=prompt, max_tokens=200)
    return response.generations[0].text.strip()


def generate_image_text_google(blog_text, q):
    messages = [
        {"role": "user",
         "parts": ["Выступи в роли промпт-инженера, создай идеальный промпт для генерации идеального изображения "
                   f"по теме {q}. Включи все необходимые условия для того, чтобы изображение получилось качественным,"
                   "без деффектов генерации, отображало тему. Это изображение в дальнейшем будет использоваться как "
                   f"обложка к статье/блогу, текст которого:{blog_text}. Выход должен быть СТРОГО МЕНЕЕ 60 токенов."
                   f"Выход должен сожержать исключительно промпт и ничего более. После генерации промпта проверь "
                   f"текст себя на ошибки и исправь их, если найдешь таковые. Промпт должен быть на английском языке"]}
    ]
    response = google_model.generate_content(messages)
    return response.to_dict()['candidates'][-1]["content"]["parts"][-1]["text"]

def generate_Dif_image(prompt, c):
    os.makedirs("results", exist_ok=True)
    os.makedirs("results/images", exist_ok=True)
    image = pipeline(prompt=prompt).images[0]
    image.save(f'results/images/dif_image_{c}.png')


def save_results(blog_text, image_text, timestamp):
    # Сохранение текста для блога в формате .docx
    os.makedirs("results", exist_ok=True)
    doc = Document()
    doc.add_paragraph(blog_text)
    doc.save(f'results/blog_text_{timestamp}.docx')

    # Сохранение текста для изображения в .txt
    with open(f'results/image_prompt_{timestamp}.txt', 'w', encoding="utf-8") as f:
        f.write(image_text)
