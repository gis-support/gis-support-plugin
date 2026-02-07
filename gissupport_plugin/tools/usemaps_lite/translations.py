from typing import Any, Dict

from qgis.PyQt.QtCore import QSettings

TRANSLATIONS = {
    "error": {
        "login": {"pl": "Błąd logowania", "en": "Login error"},
        "metadata": {"pl": "Błąd pobierania metadanych Organizacji", "en": "Error downloading Organization metadata"},
        "register": {"pl": "Błąd rejestracji", "en": "Register error"},
        "comment": {"pl": "Błąd dodawania komentarza", "en": "Send comment error"},
        "register user exists": {"pl": "Podany adres e-mail jest już w bazie użytkowników Usemaps Lite. W celu założenia nowego konta, użyj innego adresu e-mail, lub usuń konto przypisane do tego adresu (zaloguj się i usuń się z obecnej Organizacji).", "en": "The provided email address is already in the Usemaps Lite user database. To create a new account, please use a different email address or delete the account associated with this address (log in and remove yourself from the current Organization)."},
        "invite user exists": {"pl": "Zaproszony współpracownik już istnieje w Usemaps Lite. Każde konto może być przypisane tylko do jednej Organizacji. Poproś współpracownika o usunięcie konta, aby dodać go do swojej Organizacji (lub użyj innego adresu e-mail)", "en": "The invited coworker already exists in Usemaps Lite. Each account can only be assigned to one Organization. Ask the coworker to remove the account to add him to your Organization (or use a different email address)"},
        "email validation": {"pl": "Błąd walidacji adresu email", "en": "Email address validation error"},
        "password validation": {"pl": "Błąd walidacji hasła", "en": "Password validation error"},
        "password too short": {"pl": "Podane hasło jest za krótkie", "en": "Password is too short"},
        "password too long": {"pl": "Podane hasło jest za długie", "en": "Password is too long"},
        "password not equal": {"pl": "Podane hasła nie są identyczne", "en": "Passwords are not equal"},
        "invalid credentials": {"pl": "Nieprawidłowe dane logowania", "en": "Invalid login credentials"},
        "invite": {"pl": "Błąd wysyłania zaproszenia", "en": "Send invite error"},
        "remove user": {"pl": "Błąd usuwania współpracownika", "en": "Remove coworker error"},
        "load layer": {"pl": "Błąd wczytywania warstwy", "en": "Load layer error"},
        "import layer":  {"pl": "Błąd wgrywania warstwy", "en": "Upload layer error"},
        "remove layer": {"pl": "Błąd usuwania warstwy", "en": "Remove layer error"},
        "edit layer": {"pl": "Błąd edycji warstwy", "en": "Edit layer error"},
        "wrong file format": {"pl": "Zły format pliku. Proszę wybrać plik w formacie .gpkg (GeoPackage)", "en": "Wrong file format. Please select a file in .gpkg (GeoPackage) format"},
        "verification": {"pl": "Wystąpił błąd weryfikacji. Upewnij się, że podano poprawny kod.", "en": "Verification error occurred. Please make sure the correct code was entered."},
        "gpkg too large": {"pl": "Nie można przesłać pliku. Przekroczono dostępny limit przestrzeni w bazie danych (maksymalnie {mb_limit} MB)", "en": "Cannot upload the file. The available database storage limit has been exceeded (maximum {mb_limit} MB)"},
        "ogr error": {"pl": "Wystąpił błąd serwera przy wgrywaniu warstwy.", "en": "A server error occurred while uploading the layer."},
        "reset password": {"pl": "Błąd resetowania hasła", "en": "Password reset error"},
        "api error": {"pl": "Błąd połączenia z serwerem", "en": "Server connection error"},
        "limit exceeded": {"pl": "Wykorzystano dostępny limit na dane w Usemaps Lite. Aby kontynuować, usuń część danych lub skontaktuj się z zespołem GIS Support", "en": "The available data limit in Usemaps Lite has been reached. To continue, please delete some data or contact the GIS Support team"},
        "cannot load empty gpkg": {"pl": "Nie można wczytać pustego pliku GeoPackage", "en": "Cannot load empty GeoPackage file"}
    },
    "ui": {
        "info_label": {"pl": '<span style="font-size:10pt;">Usemaps Lite to narzędzie pozwalające na współpracę w QGIS. Dowiedz się więcej na <a href="https://usemaps.com/usemaps-lite/">stronie Usemaps Lite</a>.', "en": '<span style="font-size:10pt;">Usemaps Lite is the free version of the Usemaps platform for collaborative mapping. It enables easy teamwork in QGIS. Learn more on <a href="https://usemaps.com/usemaps-lite/">the Usemaps Lite website</a>.'},
        "login_button": {"pl": "Zaloguj się", "en": "Login"},
        "register_button": {"pl": "Utwórz nowe konto", "en": "Create new account"},
        "user":  {"pl": "Użytkownik", "en": "User"},
        "user_info_label": {"pl": "z organizacji", "en": "from organization"},
        "logout_button": {"pl": "Wyloguj się", "en": "Logout"},
        "events_tab": {"pl": "Powiadomienia", "en": "Notifications"},
        "layers_tab": {"pl": "Dane", "en": "Data"},
        "users_tab": {"pl": "Organizacja", "en": "Organization"},
        "recent_activities_label": {"pl": "Ostatnie aktywności", "en": "Recent activities"},
        "comment_lineedit": {"pl": "Dodaj komentarz...", "en": "Add comment..."},
        "add_comment_button": {"pl": "Wyślij", "en": "Send"},
        "available_layers_label": {"pl": "Dostępne warstwy", "en": "Available layers"},
        "layers_info_label": {"pl": "Lista warstw dostępnych dla Twojej Organizacji.  Naciśnij dwukrotnie na wybraną warstwę,  żeby ją wczytać", "en": "List of layers available to Your Organization. Double click on chosen layer to load it."},
        "import_layer_button": {"pl": "Prześlij warstwę do Usemaps Lite", "en": "Upload layer to Usemaps Lite"},
        "remove_layer_button": {"pl": "Usuń warstwę", "en": "Remove layer"},
        "used_limit_label": {"pl": "Wykorzystanie miejsca na dane", "en": "Data storage usage"},
        "coworkers": {"pl": "Współpracownicy", "en": "Coworkers"},
        "invite_user_button": {"pl": "Zaproś Współpracownika", "en": "Invite Coworker"},
        "remove_user_button": {"pl": "Usuń Współpracownika", "en": "Remove Coworker"},
        "remove user label": {"pl": "Usunięcie współpracownika", "en": "Remove coworker"},
        "remove user question": {"pl": "Czy na pewno chcesz usunąć współpracownika? Tej operacji nie da się cofnąć", "en": "Are you sure you want to remove the coworker? This operation cannot be undone"},
        "remove layer label": {"pl": "Usunięcie warstwy", "en": "Remove layer"},
        "remove layer question 1": {"pl": "Czy na pewno chcesz usunąć warstwę", "en": "Are you sure you want to remove the layer"},
        "remove layer question 2": {"pl": "? Tej operacji nie da się cofnąć", "en": "? This operation cannot be undone"},
        "invite user title": {"pl": "Zaproś współpracownika", "en": "Invite coworker"},
        "invite user label": {"pl": "W celu zaproszenia współpracownika, podaj jego e-mail. Twój współpracownik otrzyma wiadomość z prośbą o weryfikację adresu e-mail. Po weryfikacji, dołączy do Twojej organizacji.", "en": "To invite a coworker, enter their email address. Your coworker will receive a message asking them to verify their email address. Once verified, they will join Your Organization."},
        "invite": {"pl": "Zaproś", "en": "Invite"},
        "cancel": {"pl": "Anuluj", "en": "Cancel"},
        "import layer title": {"pl": "Prześlij warstwę do Usemaps Lite", "en": "Upload layer to Usemaps Lite"},
        "select_file_button": {"pl": "Wybierz plik", "en": "Select file"},
        "select_file_label": {"pl": "lub przeciągnij tutaj (GeoPackage)", "en": "or drop it here (GeoPackage)"},
        "layer_label": {"pl": "Wybierz warstwę: ", "en": "Select layer: "},
        "add": {"pl": "Dodaj", "en": "Add"},
        "login title": {"pl": "Logowanie", "en": "Login"},
        "email_label": {"pl": "Email", "en": "Email"},
        "password_label": {"pl": "Hasło", "en": "Password"},
        "login_button": {"pl": "Zaloguj", "en": "Login"},
        "register title": {"pl": "Rejestracja", "en": "Register"},
        "orgname_label": {"pl": "Nazwa konta (np. nazwa Twojej firmy.  Do konta przypisywane są dane i współpracownicy.)", "en": "Account name (e.g. your company name. Data and team members are assigned to the account.)"},
        "password_again_label": {"pl": "Powtórz hasło", "en": "Repeat password"},
        "reg_email_label": {"pl": "Twój e-mail (pierwszy współpracownik konta)", "en": "Your email (first account collaborator)"},
        "register_button": {"pl": "Utwórz nowe konto", "en": "Create new account"},
        "reg_register_button": {"pl": "Zarejestruj", "en": "Register"},
        "verify org title": {"pl": "Weryfikacja konta", "en": "Account verification"},
        "verify_label": {"pl": "Na Twój adres e-mail wysłano 6-cyfrowy kod.  Wprowadź go poniżej:","en": "A 6-digit code has been sent to your email address. Please enter it below:"},
        "terms_checkbox": {"pl": 'Akceptuję <a href="https://usemaps.com/polityka-prywatnosci/">regulamin</a>', "en": 'I accept the <a href="https://usemaps.com/polityka-prywatnosci/">Terms and Conditions</a>'},
        "code_line": {"pl": "Kod weryfikacyjny", "en": "Verification code"},
        "ok": {"pl": "Ok", "en": "Ok"},
        "verified": {"pl": "Zweryfikowany", "en": "Verified"},
        "online": {"pl": "Online", "en": "Online"},
        "select_file": {"pl": "Wybierz plik GeoPackage", "en": "Select GeoPackage file"},
        "file_filter": {"pl": "Plik GeoPackage (*.gpkg)", "en": "GeoPackage file (*.gpkg)"},
        "removed": {"pl": "usunięty", "en": "removed"},
        "password_hint_label": {"pl": 'Minimum 8 znaków', "en": 'At least 8 characters'},
        "reset pwd title": {"pl": "Resetuj hasło", "en": "Reset password"},
        "reset_pwd_info_label": {"pl": "Podaj adres email konta Usemaps Lite,  na który przesłana zostanie instrukcja resetowania hasła.", "en": "Enter the email address of the Usemaps Lite account to which the password reset instructions will be sent."},
        "reset_button": {"pl": "Resetuj", "en": "Reset"},
        "forgot_pwd_button": {"pl": "Nie pamiętasz hasła?", "en": "Forgot password?"}
    },
    "info": {
        "invited user event": {"pl": "zaproszono współpracownika", "en": "invited coworker"},
        "verified user event": {"pl": "zweryfikowano konto", "en": "account verified"},
        "deleted user event": {"pl": "usunięto współpracownika", "en": "removed coworker"},
        "uploaded layer event": {"pl": "dodano warstwę", "en": "added layer"},
        "edited layer event": {"pl": "edytowano warstwę", "en": "edited layer"},
        "added": {"pl": "dodano", "en": "added"},
        "edited": {"pl": "edytowano", "en": "edited"},
        "removed": {"pl": "usunięto", "en": "removed"},
        "deleted layer event": {"pl": "usunięto warstwę", "en": "removed layer"},
        "logged in": {"pl": "Zalogowano się", "en": "Logged in"},
        "invite send": {"pl": "Wysłano zaproszenie", "en": "Invite send"},
        "added new comment": {"pl": "dodał nowy komentarz", "en": "added new comment"},
        "is online": {"pl": "jest online", "en": "is online"},
        "is offline": {"pl": "jest offline", "en": "is offline"},
        "removed layer": {"pl": "usunął warstwę", "en": "removed layer"},
        "added layer": {"pl": "dodał warstwę", "en": "added layer"},
        "edited layer": {"pl": "edytował warstwę", "en": "edited layer"},
        "yes": {"pl": "Tak", "en": "Yes"},
        "no": {"pl": "Nie", "en": "No"},
        "removed from org": {"pl": "Twoje konto zostało usunięte z Organizacji", "en": "Your account has been removed from the Organization."},
        "load layer start": {"pl": "Rozpoczęto wczytywanie warstwy", "en": "Started loading layer"},
        "load layer success": {"pl": "Pomyślnie wczytano warstwę", "en": "Layer loaded successfully"},
        "layer loading": {"pl": "Wczytywanie warstwy", "en": "Loading layer"},
        "import layer start": {"pl": "Rozpoczęto przesyłanie warstwy", "en": "Started uploading layer"},
        "import layer success": {"pl": "Pomyślnie przesłano warstwę", "en": "Layer uploaded successfully"},
        "reset email send": {"pl": "Wysłano email resetu hasła", "en": "Password reset email has been sent"},
    }
}

class Translator:
    def __init__(self):
        self.translations = TRANSLATIONS
        self.lang = self._get_locale()

    def _get_locale(self) -> str:
        settings = QSettings()
        locale = settings.value("locale/userLocale", "en")[:2]

        if locale != 'pl':
            return 'en'

        return locale

    def translate(self, group: str, key: str) -> str:

        translation = self.translations[group][key][self.lang]

        return translation

    def translate_error(self, error_key: str, params: Dict[str, Any] = None) -> str:

        translated_text = self.translate("error", error_key)
        if params:
            translated_text = translated_text.format(**params)

        return translated_text

    def translate_ui(self, ui_key: str) -> str:

        return self.translate("ui", ui_key)

    def translate_info(self, info_key) -> str:

        return self.translate("info", info_key)

TRANSLATOR = Translator()
