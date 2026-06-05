from sentence_transformers import SentenceTransformer
import torch
def main():
    print("开始加载模型...")

    model = SentenceTransformer(
        "BAAI/bge-small-zh-v1.5"
    )

    print("模型加载成功")

    text = "今天天气不错"

    embedding = model.encode(text)

    print(f"向量维度: {len(embedding)}")
    print(f"前10个值: {embedding[:10]}")

if __name__ == "__main__":
    main()