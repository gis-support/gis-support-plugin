

class OrganizationMetadata:
    
    def __init__(self):
        self.num_of_users_limit = None
        self.logged_user_email = None
        self.mb_limit = None
        
    def set_num_of_users_limit(self, num_of_users_limit: int) -> None:
        
        self.num_of_users_limit = num_of_users_limit

    def get_num_of_users_limit(self) -> int:
        
        return self.num_of_users_limit

    def set_logged_user_email(self, logged_user_email: str) -> None:
        
        self.logged_user_email = logged_user_email

    def get_logged_user_email(self) -> str:
        
        return self.logged_user_email

    def set_mb_limit(self, limit: int) -> None:
        
        self.mb_limit = limit
    
    def get_mb_limit(self) -> int:
        
        return self.mb_limit

ORGANIZATION_METADATA = OrganizationMetadata()
