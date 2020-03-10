class BaseModule:
    """ Klasa bazowa modułów dodatkowych """

    def unload(self):
        #Funkcja wywoływana przy wyłączaniu wtyczki
        #Należy ją nadpisać w klasie dziedziczącej np. w celu zamknięcia okien dialogowych
        pass