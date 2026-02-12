try:
    from shekar import SentimentClassifier
except ImportError: 
    SentimentClassifier = None


class TextSentiment:
    def __init__(self):
        self.classifier = SentimentClassifier() if SentimentClassifier is not None else None

    def sentiment(self, text):
        normalized = str(text or "").strip().lower()
        if not normalized:
            return 0.0
        if self.classifier is None:
            return 0.0
        result = self.classifier(normalized)
        sentiment = result[1]
        if result[0] == "negative":
            sentiment = -sentiment

        return sentiment