import re
import time
import requests
import pandas as pd
import streamlit as st
from urllib.parse import quote


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.wildberries.ru/",
}


# ---------- ПОИСК WB ----------

def search_wb(query: str, page: int = 1, dest: int = -1586360):
    """
    Поиск WB.
    1. Сначала пробуем внутренний endpoint сайта.
    2. Если он не пускает, используем внешний u-search.wb.ru.
    """

    urls = [
        "https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18/search",
        "https://u-search.wb.ru/exactmatch/ru/common/v18/search",
    ]

    params = {
        "ab_testing": "false",
        "appType": 1,
        "autoselectFilters": "false",
        "curr": "rub",
        "dest": dest,
        "hide_vflags": 4294967296,
        "inheritFilters": "false",
        "lang": "ru",
        "locale": "ru",
        "page": page,
        "query": query,
        "resultset": "catalog",
        "scale": 5,
        "spp": 30,
        "suppressSpellcheck": "false",
    }

    encoded_query = quote(query)

    headers = {
        **HEADERS,
        "x-requested-with": "XMLHttpRequest",
        "x-userid": "0",
        "referer": f"https://www.wildberries.ru/catalog/0/search.aspx?search={encoded_query}",
    }

    errors = []

    for url in urls:
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=20,
            )

            if response.status_code != 200:
                errors.append(f"{url} -> статус {response.status_code}")
                continue

            data = response.json()

            products = (
                data.get("products")
                or data.get("data", {}).get("products")
                or []
            )

            if products:
                return products

            errors.append(f"{url} -> статус 200, но товаров 0")

        except Exception as e:
            errors.append(f"{url} -> {e}")

    st.warning("Поиск WB не вернул товары. Ошибки: " + " | ".join(errors))
    return []


# ---------- ФОТО ----------

def get_basket_number(nm_id: int) -> str:
    vol = int(nm_id) // 100000

    if vol <= 143:
        return "01"
    if vol <= 287:
        return "02"
    if vol <= 431:
        return "03"
    if vol <= 719:
        return "04"
    if vol <= 1007:
        return "05"
    if vol <= 1061:
        return "06"
    if vol <= 1115:
        return "07"
    if vol <= 1169:
        return "08"
    if vol <= 1313:
        return "09"
    if vol <= 1601:
        return "10"
    if vol <= 1655:
        return "11"
    if vol <= 1919:
        return "12"
    if vol <= 2045:
        return "13"
    if vol <= 2189:
        return "14"
    if vol <= 2405:
        return "15"
    if vol <= 2621:
        return "16"
    if vol <= 2837:
        return "17"
    if vol <= 3053:
        return "18"
    if vol <= 3269:
        return "19"
    if vol <= 3485:
        return "20"
    if vol <= 3701:
        return "21"
    if vol <= 3917:
        return "22"
    if vol <= 4133:
        return "23"
    if vol <= 4349:
        return "24"
    if vol <= 4565:
        return "25"
    if vol <= 4781:
        return "26"
    if vol <= 4997:
        return "27"

    return "28"


def basket_base_url(nm_id: int, basket: str):
    nm_id = int(nm_id)
    vol = nm_id // 100000
    part = nm_id // 1000

    return f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{nm_id}"


def image_url(nm_id: int):
    nm_id = int(nm_id)
    basket = get_basket_number(nm_id)
    return f"{basket_base_url(nm_id, basket)}/images/big/1.webp"


# ---------- ЦЕНА ----------

def price_from_product(product: dict):
    for key in ["salePriceU", "priceU"]:
        price = product.get(key)
        if price:
            return round(price / 100)

    sizes = product.get("sizes", [])

    if isinstance(sizes, list):
        for size in sizes:
            price_data = size.get("price", {})
            if not isinstance(price_data, dict):
                continue

            for key in ["total", "product", "basic"]:
                value = price_data.get(key)
                if value:
                    return round(value / 100)

    return None


# ---------- СОСТАВ ----------

def normalize_text(text: str) -> str:
    text = str(text).lower()
    text = text.replace("ё", "е")
    text = text.replace(",", ".")
    text = text.replace("/", " ")
    text = text.replace("\\", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_composition_value(value) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        value = ", ".join(map(str, value))

    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)

    return text


def find_composition_in_json(obj):
    """
    Ищет именно характеристику 'Состав' и возвращает только значение.
    Например: 'вискоза 70%, полиэстер 30%'
    """
    if isinstance(obj, dict):
        name = obj.get("name")
        value = obj.get("value")

        if name and normalize_text(name) == "состав":
            return clean_composition_value(value)

        for key, val in obj.items():
            if normalize_text(key) == "состав":
                return clean_composition_value(val)

        for val in obj.values():
            found = find_composition_in_json(val)
            if found:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = find_composition_in_json(item)
            if found:
                return found

    return ""


def get_card_api_details(nm_id: int):
    """
    Дополнительный источник характеристик.
    """
    urls = [
        "https://card.wb.ru/cards/v4/detail",
        "https://card.wb.ru/cards/v2/detail",
        "https://card.wb.ru/cards/detail",
    ]

    params = {
        "appType": 1,
        "curr": "rub",
        "dest": -1586360,
        "spp": 30,
        "nm": nm_id,
    }

    for url in urls:
        try:
            response = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=8,
            )

            if response.status_code != 200:
                continue

            data = response.json()

            products = (
                data.get("products")
                or data.get("data", {}).get("products")
                or []
            )

            if products:
                return products[0]

        except Exception:
            pass

    return None


def get_public_card_json(nm_id: int):
    """
    Основной источник состава:
    basket-XX.../info/ru/card.json
    """
    calculated = get_basket_number(nm_id)

    candidate_baskets = [calculated]

    for i in range(1, 36):
        basket = str(i).zfill(2)
        if basket not in candidate_baskets:
            candidate_baskets.append(basket)

    for basket in candidate_baskets:
        url = f"{basket_base_url(nm_id, basket)}/info/ru/card.json"

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=4,
            )

            if response.status_code == 200:
                return response.json()

        except Exception:
            pass

    return None


def get_composition(nm_id: int, search_product: dict):
    """
    Возвращает чистый состав.
    """
    composition = find_composition_in_json(search_product)
    if composition:
        return composition

    card_api = get_card_api_details(nm_id)
    if card_api:
        composition = find_composition_in_json(card_api)
        if composition:
            return composition

    public_card = get_public_card_json(nm_id)
    if public_card:
        composition = find_composition_in_json(public_card)
        if composition:
            return composition

    return ""


def parse_composition_percentages(composition_text: str):
    """
    Достаёт проценты вискозы и полиэстера.
    """
    text = normalize_text(composition_text)

    result = {
        "viscose": None,
        "polyester": None,
    }

    # 70% вискоза / 70 вискоза
    m = re.search(r"(\d{1,3})\s*%?\s*вискоз", text)
    if m:
        result["viscose"] = int(m.group(1))

    # вискоза 70% / вискозы 70
    m = re.search(r"вискоз\w*\s*(\d{1,3})\s*%?", text)
    if m:
        result["viscose"] = int(m.group(1))

    # 30% полиэстер / 30 полиэстер / 30 пэ
    m = re.search(r"(\d{1,3})\s*%?\s*(полиэстер|пэ|п э)", text)
    if m:
        result["polyester"] = int(m.group(1))

    # полиэстер 30% / пэ 30
    m = re.search(r"(полиэстер\w*|пэ|п э)\s*(\d{1,3})\s*%?", text)
    if m:
        result["polyester"] = int(m.group(2))

    return result


def is_70_viscose_30_polyester(composition_text: str) -> bool:
    percents = parse_composition_percentages(composition_text)

    return (
        percents["viscose"] == 70
        and percents["polyester"] == 30
    )


def composition_score(composition_text: str):
    """
    Чем выше Score, тем ближе к 70% вискоза / 30% полиэстер.
    """
    if not composition_text or composition_text == "состав не найден":
        return -999

    percents = parse_composition_percentages(composition_text)

    viscose = percents["viscose"]
    polyester = percents["polyester"]

    if viscose is None and polyester is None:
        return -500

    score = 100

    if viscose is not None:
        score -= abs(viscose - 70) * 2
    else:
        score -= 80

    if polyester is not None:
        score -= abs(polyester - 30) * 2
    else:
        score -= 80

    return score


def composition_status(composition_text: str):
    if not composition_text or composition_text == "состав не найден":
        return "состав не найден"

    percents = parse_composition_percentages(composition_text)

    viscose = percents["viscose"]
    polyester = percents["polyester"]

    if viscose == 70 and polyester == 30:
        return "точное совпадение 70/30"

    if viscose is not None and polyester is not None:
        return f"вискоза {viscose}%, полиэстер {polyester}%"

    if viscose is not None:
        return f"вискоза {viscose}%, полиэстер не найден"

    if polyester is not None:
        return f"полиэстер {polyester}%, вискоза не найдена"

    return "проценты не распознаны"


# ---------- ОБРАБОТКА ТОВАРОВ ----------

def make_rows(products, check_composition_limit: int):
    rows = []
    seen_ids = set()

    unique_products = []

    for product in products:
        nm_id = product.get("id") or product.get("nmId")

        if not nm_id:
            continue

        if nm_id in seen_ids:
            continue

        seen_ids.add(nm_id)
        unique_products.append(product)

    total = len(unique_products)

    if total == 0:
        return []

    progress = st.progress(0)
    status = st.empty()

    for index, product in enumerate(unique_products, start=1):
        nm_id = product.get("id") or product.get("nmId")

        if index <= check_composition_limit:
            status.write(f"Проверяю состав: {index} из {min(total, check_composition_limit)}")
            composition = get_composition(nm_id, product)
            time.sleep(0.05)
        else:
            composition = ""

        composition_clean = composition if composition else "состав не найден"

        rows.append({
            "Фото": image_url(nm_id),
            "Название": product.get("name"),
            "Бренд": product.get("brand"),
            "Цена, ₽": price_from_product(product),
            "Рейтинг": product.get("reviewRating") or product.get("rating"),
            "Отзывы": product.get("feedbacks"),
            "Артикул WB": nm_id,
            "Состав": composition_clean,
            "Статус состава": composition_status(composition_clean),
            "Score": composition_score(composition_clean),
            "Подходит 70/30": is_70_viscose_30_polyester(composition_clean),
            "Ссылка": f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx",
        })

        progress.progress(index / total)

    status.empty()
    progress.empty()

    return rows


# ---------- STREAMLIT UI ----------

st.set_page_config(
    page_title="Поиск WB с проверкой состава",
    layout="wide",
)

st.title("Поиск Wildberries с проверкой состава")

query = st.text_input(
    "Что ищем?",
    value="70 вискоза 30 полиэстер боксеры",
)

pages = st.slider(
    "Сколько страниц поиска проверить",
    min_value=1,
    max_value=10,
    value=1,
)

check_composition_limit = st.slider(
    "У скольких товаров проверять состав",
    min_value=1,
    max_value=300,
    value=300,
)

only_target_composition = st.checkbox(
    "Показывать только 70% вискоза / 30% полиэстер",
    value=False,
)

dest_input = st.text_input(
    "WB dest",
    value="-1586360",
    help="Иваново: -1586360"
)

try:
    dest = int(dest_input)
except ValueError:
    dest = -1586360

if st.button("Найти"):
    all_products = []

    st.write(f"WB dest: **{dest}**")

    with st.spinner("Ищу товары на Wildberries..."):
        for page in range(1, pages + 1):
            products = search_wb(query, page, dest=dest)
            all_products.extend(products)

    st.write(f"Найдено товаров в выдаче: {len(all_products)}")

    if not all_products:
        st.warning("WB ничего не вернул по этому запросу.")
    else:
        rows = make_rows(
            products=all_products,
            check_composition_limit=check_composition_limit,
        )

        df = pd.DataFrame(rows)

        if not df.empty and "Score" in df.columns:
            df = df.sort_values(
                by=["Подходит 70/30", "Score"],
                ascending=[False, False],
            )

        if only_target_composition:
            df = df[df["Подходит 70/30"] == True]

        st.write(f"Показано товаров: {len(df)}")

        if df.empty:
            st.warning("После фильтрации ничего не осталось.")
        else:
            for _, row in df.iterrows():
                col1, col2 = st.columns([1, 4])

                with col1:
                    st.image(row["Фото"], width=170)

                with col2:
                    st.subheader(row["Название"])

                    st.write(f"**Бренд:** {row['Бренд']}")
                    st.write(f"**Цена:** {row['Цена, ₽']} ₽")
                    st.write(f"**Рейтинг:** {row['Рейтинг']}")
                    st.write(f"**Отзывы:** {row['Отзывы']}")
                    st.write(f"**Артикул WB:** {row['Артикул WB']}")

                    if row["Подходит 70/30"]:
                        st.success(f"Состав: {row['Состав']}")
                    elif row["Состав"] == "состав не найден":
                        st.warning("Состав не найден")
                    else:
                        st.info(f"Состав: {row['Состав']}")

                    st.write(f"**Статус состава:** {row['Статус состава']}")
                    st.write(f"**Оценка близости:** {row['Score']}")

                    st.link_button("Открыть на WB", row["Ссылка"])

                st.divider()

            csv = df.to_csv(index=False).encode("utf-8-sig")

            st.download_button(
                "Скачать CSV",
                data=csv,
                file_name="wb_search_with_composition.csv",
                mime="text/csv",
            )