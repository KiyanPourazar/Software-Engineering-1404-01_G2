from shekar import SentimentClassifier

class TextSentiment:
    def __init__(self):
        self.classifier = SentimentClassifier()

    def sentiment(self, text):
        result = self.classifier(text)
        sentiment = result[1]
        if result[0] == "negative":
            sentiment = -sentiment

        return sentiment