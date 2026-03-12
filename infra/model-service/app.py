from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title='Mock OpenAI Compatible Model Service')


class Message(BaseModel):
    role: str
    content: str


class CompletionRequest(BaseModel):
    model: str
    messages: list[Message]


def classify(content: str) -> dict:
    lowered = content.lower()
    if 'kfc' in lowered or '咖啡' in lowered or '奶茶' in lowered or '餐' in lowered:
        category = '餐饮'
    elif '地铁' in lowered or '滴滴' in lowered or '火车' in lowered:
        category = '交通'
    elif '工资' in lowered or '收入' in lowered:
        category = '收入'
    elif '房租' in lowered or '物业' in lowered:
        category = '住房'
    else:
        category = '未分类'
    return {
        'category': category,
        'subcategory': None,
        'confidence': 0.72 if category == '未分类' else 0.88,
        'reason': 'mock local model response',
    }


@app.post('/v1/chat/completions')
def chat_completions(payload: CompletionRequest) -> dict:
    text = '\n'.join(message.content for message in payload.messages)
    result = classify(text)
    return {
        'id': 'mock-chatcmpl-1',
        'object': 'chat.completion',
        'choices': [
            {
                'index': 0,
                'message': {
                    'role': 'assistant',
                    'content': __import__('json').dumps(result, ensure_ascii=False),
                },
                'finish_reason': 'stop',
            }
        ],
    }
