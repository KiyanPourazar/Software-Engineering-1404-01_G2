import pandas as pd
from surprise import Dataset, Reader, SVD
from team5.exceptions.not_trained_yet_exception import NotTrainedYetException

class RecommenderModel:
    def __init__(self, rating_scale: tuple[int|float, int|float]=(1, 2), n_factors=20, n_epochs=20, lr_all=0.005, reg_all=0.02):
        self.model = None
        self.items = set([])
        self.user_item_rating_matrix = pd.DataFrame()
        self.rating_scale = rating_scale
        self.n_factors = n_factors
        self.n_epochs = n_epochs
        self.lr_all = lr_all
        self.reg_all = reg_all


    def train(self, train_data: list[tuple[str, str, int|float]]):
        df = pd.DataFrame(train_data, columns=["userID", "itemID", "rating"])
        self.items = self.items.union(set(df["itemID"]))
        self._update_user_item_rating_matrix(df)

        reader = Reader(rating_scale=self.rating_scale)
        data = Dataset.load_from_df(df, reader)
        trainset = data.build_full_trainset()

        algo = SVD(n_factors=self.n_factors, n_epochs=self.n_epochs, lr_all=self.lr_all, reg_all=self.reg_all)
        algo.fit(trainset)

        self.model = algo

    def predict_rating(self, user_id, item_id):
        return self.model.predict(user_id, item_id)

    def recommend(self, user_id, top_n=3, show_already_seen_items=False):
        possible_items = self._get_possible_items(user_id, show_already_seen_items)
        return self._get_predictions(user_id, possible_items, top_n)


    def _update_user_item_rating_matrix(self, new_user_item_rating: pd.DataFrame):
        new_matrix = new_user_item_rating.pivot_table(index="userID", columns="itemID", values="rating")
        self._combine_with_matrix(new_matrix)

    def _combine_with_matrix(self, new_matrix: pd.DataFrame):
        if self.user_item_rating_matrix.empty:
            self.user_item_rating_matrix = new_matrix
        else:
            # Combine with existing matrix and keep latest ratings
            self.user_item_rating_matrix = (
                pd.concat([self.user_item_rating_matrix, new_matrix])
                .groupby(level=0)
                .last()
            )

    def _get_possible_items(self, user_id, show_already_seen_items):
        if show_already_seen_items:
            possible_items = self.items
        else:
            if user_id in self.user_item_rating_matrix.index:
                seen_items = set(
                    self.user_item_rating_matrix.loc[user_id]
                    .dropna()
                    .index
                )
            else:
                seen_items = set()

            possible_items = self.items - seen_items
        return possible_items
    
    def _get_predictions(self, user_id, possible_items, top_n):
        if self.model is None:
            raise NotTrainedYetException()
        
        predictions = []
        for item in possible_items:
            pred = self.model.predict(user_id, item)
            predictions.append((item, pred.est))
        
        predictions.sort(key=lambda x: x[1], reverse=True)
        
        return predictions[:top_n]