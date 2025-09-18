from sentence_transformers import SentenceTransformer, util
from sklearn.metrics.pairwise import cosine_similarity
import config

MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
print(f"Загрузка языковой модели '{MODEL_NAME}'...")
model = SentenceTransformer(MODEL_NAME)
print("Модель успешно загружена.")

SIMILARITY_THRESHOLD = 0.60

def find_best_faq_match(user_question, all_faq_items):
    """
    Находит наиболее подходящий вопрос из FAQ, используя семантическую схожесть.
    """
    if not all_faq_items:
        return None

    faq_questions = [item[0] for item in all_faq_items]

    user_embedding = model.encode(user_question)
    faq_embeddings = model.encode(faq_questions)

    similarities = cosine_similarity([user_embedding], faq_embeddings)[0]

    best_match_index = similarities.argmax()
    best_match_score = similarities[best_match_index]

    if config.DEBUG_FAQ_MATCHING:
        print(f"Поиск по FAQ: '{user_question}' -> '{faq_questions[best_match_index]}' (Схожесть: {best_match_score:.2f})")

    if best_match_score >= SIMILARITY_THRESHOLD:
        return all_faq_items[best_match_index]
    
    return None