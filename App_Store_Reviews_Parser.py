import streamlit as st
import pandas as pd
import re
import time
import random
import requests
from datetime import datetime
import warnings
from bs4 import BeautifulSoup
import json
warnings.filterwarnings('ignore')

# Настройки страницы
st.set_page_config(
    page_title="Парсер отзывов App Store",
    page_icon="🍎",
    layout="wide"
)

# Стилизация
st.markdown("""
<style>
    .stButton button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
    }
    .rating-5 { color: #4CAF50; font-weight: bold; }
    .rating-4 { color: #8BC34A; font-weight: bold; }
    .rating-3 { color: #FFC107; font-weight: bold; }
    .rating-2 { color: #FF9800; font-weight: bold; }
    .rating-1 { color: #f44336; font-weight: bold; }
    .review-card {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        border-left: 4px solid #4CAF50;
    }
    .stat-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    .stat-number {
        font-size: 36px;
        font-weight: bold;
        color: #4CAF50;
    }
</style>
""", unsafe_allow_html=True)

def extract_app_id_and_country(url):
    """Извлекает ID приложения и страну из ссылки App Store."""
    try:
        country_match = re.search(r'apps\.apple\.com/([a-z]{2})/', url)
        if country_match:
            country = country_match.group(1)
        else:
            country = 'us'

        id_match = re.search(r'/id(\d+)', url)
        if id_match:
            app_id = id_match.group(1)
            return app_id, country
        return None, None
    except Exception:
        return None, None

def scrape_reviews_via_appstore_api(app_id, country, max_reviews=500):
    """Собирает отзывы через альтернативный API App Store."""
    reviews = []
    seen_review_ids = set()
    seen_content_hashes = set()
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'X-Apple-Store-Front': f'{country},32'
    }
    
    page = 0
    duplicates_found = 0
    
    while len(reviews) < max_reviews and page < 10:
        try:
            # Используем iTunes Search API для получения отзывов
            url = f"https://itunes.apple.com/{country}/rss/customerreviews/page={page+1}/id={app_id}/sortby=mostrecent/json?cc={country}&l=en"
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'feed' in data and 'entry' in data['feed']:
                    entries = data['feed']['entry']
                    
                    # Пропускаем первый элемент, если это информация о приложении
                    if len(entries) > 0 and page == 0:
                        if 'im:name' in entries[0] and 'im:artist' in entries[0]:
                            entries = entries[1:]
                    
                    for entry in entries:
                        if len(reviews) >= max_reviews:
                            break
                        
                        try:
                            # Получаем ID отзыва
                            review_id = entry.get('id', {}).get('label', '')
                            
                            # Получаем текст и заголовок
                            content = entry.get('content', {}).get('label', '')
                            title = entry.get('title', {}).get('label', '')
                            
                            # Проверка на дубликаты
                            content_hash = hash(f"{content}_{title}") if content else None
                            
                            if review_id and review_id in seen_review_ids:
                                duplicates_found += 1
                                continue
                            if content_hash and content_hash in seen_content_hashes:
                                duplicates_found += 1
                                continue
                            
                            # Получаем остальные данные
                            user_name = entry.get('author', {}).get('name', {}).get('label', 'Anonymous')
                            date_str = entry.get('updated', {}).get('label', '')
                            date = date_str.split('T')[0] if date_str else 'N/A'
                            
                            rating = 0
                            if 'im:rating' in entry:
                                rating = int(entry.get('im:rating', {}).get('label', 0))
                            
                            review_text = entry.get('content', {}).get('label', '').strip()
                            title_text = entry.get('title', {}).get('label', '').strip()
                            app_version = entry.get('im:version', {}).get('label', 'N/A')
                            
                            stars = '★' * rating + '☆' * (5 - rating)
                            
                            review_data = {
                                '№': len(reviews) + 1,
                                'Дата': date,
                                'Оценка (число)': rating,
                                'Оценка (звезды)': stars,
                                'Пользователь': user_name,
                                'Заголовок': title_text if title_text else '(без заголовка)',
                                'Текст отзыва': review_text if review_text else '(текст отсутствует)',
                                'Версия': app_version
                            }
                            
                            reviews.append(review_data)
                            if review_id:
                                seen_review_ids.add(review_id)
                            if content_hash:
                                seen_content_hashes.add(content_hash)
                            
                            progress = min(len(reviews) / max_reviews, 1.0)
                            progress_bar.progress(progress)
                            status_text.text(f"Собрано отзывов: {len(reviews)} | Страница: {page+1} | Уникальных: {len(reviews)}")
                            
                        except Exception as e:
                            continue
                    
                    if len(entries) < 10:  # Если страница неполная, значит это последняя
                        break
                        
                    time.sleep(random.uniform(1, 2))
                    page += 1
                else:
                    break
            else:
                break
                
        except Exception as e:
            break
    
    # Если не нашли отзывы через RSS, пробуем альтернативный метод
    if len(reviews) == 0:
        reviews = scrape_reviews_via_appstore_web(app_id, country, max_reviews)
    
    progress_bar.empty()
    status_text.empty()
    
    return reviews

def scrape_reviews_via_appstore_web(app_id, country, max_reviews=500):
    """Альтернативный метод сбора отзывов через веб-интерфейс."""
    reviews = []
    
    try:
        # Используем другой эндпоинт
        url = f"https://apps.apple.com/{country}/app/id{app_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Парсим HTML для поиска данных
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем скрипт с данными
            scripts = soup.find_all('script', type='application/json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    # Здесь логика парсинга зависит от структуры страницы
                    # Этот метод сложнее и требует анализа структуры конкретного приложения
                    pass
                except:
                    continue
                    
    except Exception as e:
        pass
    
    return reviews

def scrape_reviews_using_itunes_api(app_id, country, max_reviews=500):
    """Использование iTunes Lookup API."""
    reviews = []
    
    try:
        # Получаем общую информацию о приложении
        lookup_url = f"https://itunes.apple.com/lookup?id={app_id}&country={country}"
        response = requests.get(lookup_url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('resultCount', 0) > 0:
                app_info = data['results'][0]
                total_reviews = app_info.get('userRatingCountForCurrentVersion', 0)
                st.info(f"Всего отзывов в текущей версии: {total_reviews}")
                
                # К сожалению, Lookup API не возвращает текст отзывов
                # только общую статистику
                
    except Exception as e:
        pass
    
    return reviews

@st.cache_data(ttl=3600)
def scrape_app_reviews(app_id, country, max_reviews=500):
    """Главная функция сбора отзывов с несколькими методами."""
    
    # Пробуем разные методы
    methods = [
        ("RSS API", scrape_reviews_via_appstore_api),
        ("iTunes API", scrape_reviews_using_itunes_api)
    ]
    
    for method_name, method_func in methods:
        st.info(f"Пробуем метод {method_name}...")
        reviews = method_func(app_id, country, max_reviews)
        
        if reviews and len(reviews) > 0:
            st.success(f"Метод {method_name} успешно собрал {len(reviews)} отзывов")
            return reviews
    
    # Если отзывы не найдены, показываем тестовые данные для демонстрации
    st.warning("Не удалось получить реальные отзывы. Отображаются демонстрационные данные.")
    return get_demo_reviews(app_id, country)

def get_demo_reviews(app_id, country):
    """Создает демонстрационные данные для тестирования."""
    demo_reviews = []
    
    sample_reviews = [
        {"date": "2024-01-15", "rating": 5, "title": "Отличное приложение!", "content": "Очень удобно и полезно. Рекомендую всем!", "user": "User123", "version": "2.0.1"},
        {"date": "2024-01-14", "rating": 4, "title": "Хорошо, но есть баги", "content": "Приложение хорошее, но иногда вылетает", "user": "IvanPetrov", "version": "2.0.0"},
        {"date": "2024-01-13", "rating": 5, "title": "Супер!", "content": "Лучшее приложение в своем роде", "user": "MarinaS", "version": "2.0.1"},
        {"date": "2024-01-12", "rating": 3, "title": "Нормально", "content": "Среднее приложение, есть над чем работать", "user": "DmitryK", "version": "1.9.9"},
        {"date": "2024-01-11", "rating": 2, "title": "Разочарован", "content": "Не соответствует ожиданиям", "user": "AlexeyR", "version": "1.9.8"},
        {"date": "2024-01-10", "rating": 5, "title": "Отлично!", "content": "Все работает как надо", "user": "ElenaVolkova", "version": "2.0.1"},
        {"date": "2024-01-09", "rating": 4, "title": "Неплохо", "content": "Интерфейс удобный, но хотелось бы больше функций", "user": "SergeyN", "version": "2.0.0"},
        {"date": "2024-01-08", "rating": 5, "title": "Замечательное приложение", "content": "Пользуюсь каждый день", "user": "AnnaSmirnova", "version": "2.0.1"},
    ]
    
    for i, review in enumerate(sample_reviews[:min(len(sample_reviews), 100)], 1):
        stars = '★' * review['rating'] + '☆' * (5 - review['rating'])
        review_data = {
            '№': i,
            'Дата': review['date'],
            'Оценка (число)': review['rating'],
            'Оценка (звезды)': stars,
            'Пользователь': review['user'],
            'Заголовок': review['title'],
            'Текст отзыва': review['content'],
            'Версия': review['version']
        }
        demo_reviews.append(review_data)
    
    return demo_reviews

def main():
    st.title("🍎 Парсер отзывов App Store")
    st.markdown("---")
    
    # Информация об ограничениях API
    with st.expander("ℹ️ Важная информация об API App Store"):
        st.markdown("""
        **Ограничения Apple API:**
        - Apple RSS API возвращает **только последние 500 отзывов** для каждого приложения
        - API может не возвращать отзывы для новых приложений
        - Для некоторых регионов API может работать некорректно
        - **Рекомендация:** Используйте специальные сервисы парсинга для больших объемов данных
        
        **Альтернативы:**
        - App Annie
        - Sensor Tower
        - AppTweak
        """)
    
    # Боковая панель для ввода данных
    with st.sidebar:
        st.header("📱 Настройки")
        
        url = st.text_input(
            "Ссылка на приложение",
            placeholder="https://apps.apple.com/us/app/duolingo-language-lessons/id570060128",
            help="Вставьте полную ссылку на приложение в App Store"
        )
        
        max_reviews = st.select_slider(
            "Количество отзывов",
            options=[50, 100, 200, 500],
            value=100,
            help="Максимальное количество отзывов (Apple API обычно возвращает не более 500)"
        )
        
        use_demo = st.checkbox("Использовать демо-данные (для тестирования)", value=False)
        
        start_button = st.button("🚀 Начать сбор", type="primary", disabled=not url and not use_demo)
    
    # Основной контент
    if start_button:
        if use_demo:
            st.info("🎭 Используются демонстрационные данные для тестирования")
            app_id = "570060128"
            country = "us"
            reviews = get_demo_reviews(app_id, country)
            
        elif url:
            app_id, country = extract_app_id_and_country(url)
            
            if not app_id:
                st.error("❌ Не удалось извлечь ID приложения из ссылки")
                st.info("Пример правильной ссылки: https://apps.apple.com/ru/app/id570060128")
                return
            
            st.info(f"📱 ID приложения: `{app_id}` | 🌍 Страна: `{country.upper()}`")
            
            with st.spinner("Сбор отзывов... Это может занять несколько минут..."):
                reviews = scrape_app_reviews(app_id, country, max_reviews=max_reviews)
        else:
            st.warning("⚠️ Пожалуйста, введите ссылку на приложение или используйте демо-режим")
            return
        
        if not reviews:
            st.warning("❌ Отзывы не найдены. Попробуйте использовать демо-режим для тестирования интерфейса.")
            return
        
        # Сохраняем в session state
        st.session_state['reviews'] = reviews
        
        st.success(f"✅ Успешно собрано {len(reviews)} уникальных отзывов!")
        
        # Создаем DataFrame
        df = pd.DataFrame(reviews)
        
        # Статистика
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Всего отзывов", len(df))
        
        with col2:
            avg_rating = df['Оценка (число)'].mean()
            st.metric("Средний рейтинг", f"{avg_rating:.2f} ★")
        
        with col3:
            positive = len(df[df['Оценка (число)'] >= 4])
            st.metric("Положительные (4-5★)", f"{positive} ({positive/len(df)*100:.1f}%)")
        
        with col4:
            negative = len(df[df['Оценка (число)'] <= 2])
            st.metric("Отрицательные (1-2★)", f"{negative} ({negative/len(df)*100:.1f}%)")
        
        # Распределение оценок
        st.subheader("📊 Распределение оценок")
        
        rating_dist = df['Оценка (число)'].value_counts().sort_index(ascending=False)
        chart_data = pd.DataFrame({
            'Оценка': [f"{r} ★" for r in rating_dist.index],
            'Количество': rating_dist.values
        })
        st.bar_chart(chart_data.set_index('Оценка'))
        
        # Даты
        if len(df) > 0 and df['Дата'].min() != 'N/A':
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"📅 Период: с **{df['Дата'].min()}** по **{df['Дата'].max()}**")
            with col2:
                try:
                    days_diff = (pd.to_datetime(df['Дата'].max()) - pd.to_datetime(df['Дата'].min())).days
                    if days_diff > 0:
                        st.info(f"📊 В среднем: **{len(df)/days_diff:.1f}** отзывов в день")
                except:
                    pass
        
        st.markdown("---")
        
        # Фильтры
        st.subheader("🔍 Фильтрация отзывов")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            rating_filter = st.multiselect(
                "Оценка",
                options=[5, 4, 3, 2, 1],
                default=[5, 4, 3, 2, 1],
                format_func=lambda x: f"{x} ★"
            )
        
        with col2:
            search_text = st.text_input("Поиск по тексту", placeholder="Введите слово или фразу...")
        
        with col3:
            if 'Дата' in df.columns and df['Дата'].iloc[0] != 'N/A':
                try:
                    date_range = st.date_input(
                        "Период",
                        value=[pd.to_datetime(df['Дата']).min(), pd.to_datetime(df['Дата']).max()]
                    )
                except:
                    date_range = []
            else:
                date_range = []
        
        # Применяем фильтры
        filtered_df = df[df['Оценка (число)'].isin(rating_filter)]
        
        if search_text:
            filtered_df = filtered_df[
                filtered_df['Текст отзыва'].str.contains(search_text, case=False, na=False) |
                filtered_df['Заголовок'].str.contains(search_text, case=False, na=False)
            ]
        
        if len(date_range) == 2:
            try:
                filtered_df = filtered_df[
                    (pd.to_datetime(filtered_df['Дата']) >= pd.to_datetime(date_range[0])) &
                    (pd.to_datetime(filtered_df['Дата']) <= pd.to_datetime(date_range[1]))
                ]
            except:
                pass
        
        st.info(f"📄 Показано отзывов: {len(filtered_df)} из {len(df)}")
        
        # Отображение отзывов
        st.subheader("💬 Отзывы")
        
        # Выбор режима отображения
        view_mode = st.radio("Режим отображения", ["Компактный (таблица)", "Подробный (карточки)"], horizontal=True)
        
        if view_mode == "Компактный (таблица)":
            display_df = filtered_df[['Дата', 'Оценка (звезды)', 'Заголовок', 'Текст отзыва', 'Пользователь', 'Версия']].copy()
            display_df.columns = ['Дата', 'Оценка', 'Заголовок', 'Текст', 'Пользователь', 'Версия']
            st.dataframe(display_df, use_container_width=True, height=400)
        else:
            for idx, row in filtered_df.iterrows():
                rating_class = f"rating-{row['Оценка (число)']}"
                st.markdown(f"""
                <div class="review-card">
                    <strong>{row['Дата']}</strong> | <span class="{rating_class}">{row['Оценка (звезды)']}</span><br>
                    <strong>📌 {row['Заголовок']}</strong><br>
                    {row['Текст отзыва']}<br>
                    <small>👤 {row['Пользователь']} | 📱 Версия: {row['Версия']}</small>
                </div>
                """, unsafe_allow_html=True)
        
        # Экспорт данных
        st.markdown("---")
        st.subheader("💾 Экспорт данных")
        
        col1, col2 = st.columns(2)
        
        with col1:
            csv = filtered_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Скачать отфильтрованные отзывы (CSV)",
                data=csv,
                file_name=f"app_reviews_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            try:
                from io import BytesIO
                import openpyxl
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    filtered_df.to_excel(writer, sheet_name='Отфильтрованные отзывы', index=False)
                    
                    # Статистика
                    stats_df = pd.DataFrame({
                        'Показатель': [
                            'Всего отзывов',
                            'Средний рейтинг',
                            'Положительные (4-5★)',
                            'Нейтральные (3★)',
                            'Отрицательные (1-2★)'
                        ],
                        'Значение': [
                            len(filtered_df),
                            f"{filtered_df['Оценка (число)'].mean():.2f}",
                            len(filtered_df[filtered_df['Оценка (число)'] >= 4]),
                            len(filtered_df[filtered_df['Оценка (число)'] == 3]),
                            len(filtered_df[filtered_df['Оценка (число)'] <= 2])
                        ]
                    })
                    stats_df.to_excel(writer, sheet_name='Статистика', index=False)
                
                output.seek(0)
                st.download_button(
                    label="📊 Скачать как Excel",
                    data=output,
                    file_name=f"app_reviews_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except:
                st.warning("Экспорт в Excel недоступен. Используйте CSV формат.")
    
    elif not url and not start_button:
        st.info("👈 Введите ссылку на приложение или включите демо-режим для тестирования")
        
        # Пример
        with st.expander("ℹ️ Как получить ссылку на приложение"):
            st.markdown("""
            1. Откройте [App Store](https://www.apple.com/app-store/)
            2. Найдите нужное приложение
            3. Скопируйте ссылку из адресной строки браузера
            4. Пример ссылки: `https://apps.apple.com/ru/app/id570060128`
            
            **Важно:** ID приложения находится в конце ссылки после `/id`
            
            **Ограничения парсинга:**
            - Apple официально не предоставляет открытого API для получения отзывов
            - Доступный RSS API имеет ограничения и может не работать для некоторых приложений
            - Для коммерческого использования рекомендуется использовать платные сервисы
            """)

if __name__ == "__main__":
    main()
