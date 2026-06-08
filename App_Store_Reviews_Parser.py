import streamlit as st
import pandas as pd
import re
import time
import random
import requests
from datetime import datetime
import warnings
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

@st.cache_data(ttl=3600)
def scrape_app_reviews(app_id, country, max_reviews=500):
    """Собирает отзывы через API Apple с фильтрацией дубликатов."""
    reviews = []
    seen_review_ids = set()
    seen_content_hashes = set()

    progress_bar = st.progress(0)
    status_text = st.empty()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json'
    }

    page = 1
    consecutive_empty = 0
    max_pages = 50
    total_entries_processed = 0
    duplicates_found = 0

    while len(reviews) < max_reviews and consecutive_empty < 5 and page <= max_pages:
        try:
            url = f"https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                break

            data = response.json()
            
            if 'feed' not in data or 'entry' not in data['feed']:
                consecutive_empty += 1
                page += 1
                time.sleep(random.uniform(0.5, 1))
                continue

            entries = data['feed']['entry']
            
            if page == 1 and len(entries) > 0:
                if 'im:name' in entries[0] and 'im:artist' in entries[0]:
                    entries = entries[1:]

            if not entries:
                consecutive_empty += 1
                page += 1
                continue

            consecutive_empty = 0
            new_unique_reviews = 0
            
            for entry in entries:
                if len(reviews) >= max_reviews:
                    break
                
                total_entries_processed += 1
                
                try:
                    review_id = entry.get('id', {}).get('label', '')
                    content = entry.get('content', {}).get('label', '')
                    title = entry.get('title', {}).get('label', '')
                    content_hash = hash(f"{content}_{title}") if content else None
                    
                    is_duplicate = False
                    if review_id and review_id in seen_review_ids:
                        is_duplicate = True
                    elif content_hash and content_hash in seen_content_hashes:
                        is_duplicate = True
                    
                    if is_duplicate:
                        duplicates_found += 1
                        continue
                    
                    user_name = entry.get('author', {}).get('name', {}).get('label', 'Аноним')
                    date_str = entry.get('updated', {}).get('label', '')
                    date = date_str.split('T')[0] if date_str else 'N/A'
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
                    
                    new_unique_reviews += 1
                    
                    progress = min(len(reviews) / max_reviews, 1.0)
                    progress_bar.progress(progress)
                    status_text.text(f"Собрано отзывов: {len(reviews)} | Страница: {page} | Дублей: {duplicates_found}")

                except Exception:
                    continue

            if new_unique_reviews == 0 and len(entries) > 0:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    break
            
            if len(entries) < 10:
                break
            
            time.sleep(random.uniform(1.5, 2.5))
            page += 1

        except Exception:
            break

    progress_bar.empty()
    status_text.empty()
    
    return reviews

def main():
    st.title("🍎 Парсер отзывов App Store")
    st.markdown("---")
    
    # Боковая панель для ввода данных
    with st.sidebar:
        st.header("📱 Настройки")
        
        url = st.text_input(
            "Ссылка на приложение",
            placeholder="https://apps.apple.com/ru/app/id570060128",
            help="Вставьте полную ссылку на приложение в App Store"
        )
        
        max_reviews = st.select_slider(
            "Количество отзывов",
            options=[100, 300, 500, 1000],
            value=500,
            help="Максимальное количество уникальных отзывов (API часто возвращает меньше)"
        )
        
        start_button = st.button("🚀 Начать сбор", type="primary", disabled=not url)
    
    # Основной контент
    if start_button and url:
        app_id, country = extract_app_id_and_country(url)
        
        if not app_id:
            st.error("❌ Не удалось извлечь ID приложения из ссылки")
            st.info("Пример правильной ссылки: https://apps.apple.com/ru/app/id570060128")
            return
        
        st.info(f"📱 ID приложения: `{app_id}` | 🌍 Страна: `{country.upper()}`")
        
        with st.spinner("Сбор отзывов... Это может занять несколько минут..."):
            reviews = scrape_app_reviews(app_id, country, max_reviews=max_reviews)
        
        if not reviews:
            st.warning("❌ Отзывы не найдены. Возможно, у приложения нет отзывов или API вернул пустой ответ.")
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
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"📅 Период: с **{df['Дата'].min()}** по **{df['Дата'].max()}**")
        with col2:
            days_diff = (pd.to_datetime(df['Дата'].max()) - pd.to_datetime(df['Дата'].min())).days
            if days_diff > 0:
                st.info(f"📊 В среднем: **{len(df)/days_diff:.1f}** отзывов в день")
        
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
            date_range = st.date_input(
                "Период",
                value=[pd.to_datetime(df['Дата']).min(), pd.to_datetime(df['Дата']).max()]
            )
        
        # Применяем фильтры
        filtered_df = df[df['Оценка (число)'].isin(rating_filter)]
        
        if search_text:
            filtered_df = filtered_df[
                filtered_df['Текст отзыва'].str.contains(search_text, case=False, na=False) |
                filtered_df['Заголовок'].str.contains(search_text, case=False, na=False)
            ]
        
        if len(date_range) == 2:
            filtered_df = filtered_df[
                (pd.to_datetime(filtered_df['Дата']) >= pd.to_datetime(date_range[0])) &
                (pd.to_datetime(filtered_df['Дата']) <= pd.to_datetime(date_range[1]))
            ]
        
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
            # Создаем Excel с несколькими листами
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
    
    elif not url and start_button:
        st.warning("⚠️ Пожалуйста, введите ссылку на приложение")
    else:
        st.info("👈 Введите ссылку на приложение в боковой панели и нажмите 'Начать сбор'")
        
        # Пример
        with st.expander("ℹ️ Как получить ссылку на приложение"):
            st.markdown("""
            1. Откройте [App Store](https://www.apple.com/app-store/)
            2. Найдите нужное приложение
            3. Скопируйте ссылку из адресной строки браузера
            4. Пример ссылки: `https://apps.apple.com/ru/app/id570060128`
            
            **Важно:** ID приложения находится в конце ссылки после `/id`
            """)

if __name__ == "__main__":
    main()