from srch import *
from datetime import datetime

if __name__ == "__main__":
    news = search_news("Насколько важно обучать детей арифметике и скорочтению как можно раньше")
    news = news + search_news("news about early math and reading education for kids",
                              tbm="nws")
    blog_text = generate_blog_text_mult(news)
    image_text = generate_image_text(blog_text)
    save_results(blog_text, image_text)
    generate_Dif_image(image_text, datetime.now().strftime('%Y%m%d_%H%M%S'))
