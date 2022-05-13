

class sigchoice:
    def __init__(self, value: int, name: str, name_en: str = "", comment_fr: str = "", comment_en: str = ""):
        self.name = name
        self.name_en = name_en
        self.comment_fr = comment_fr
        self.comment_en = comment_en
        self.value = value