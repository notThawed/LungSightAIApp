from PyQt6.QtWidgets import QDialog
from ..base_window import UiLoader
from .manage_user import ManageUsers

class Superadmin_Window(QDialog, UiLoader):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.load_ui("super_admin/super_admin_window.ui")
        # print(self.user.get("role"))
        
        #CONTROLLERS
        self.manage_users_controller = ManageUsers(self)

        self.user_label.setText(self.user['first_name'].upper())

        self.stackedWidget.setCurrentWidget(self.default_page)


        self.manage_users_button.clicked.connect(self.open_manage_users)

        self.configure_button.clicked.connect(
            lambda:self.stackedWidget.setCurrentWidget(self.configure_system)
        )

        self.view_reports_button.clicked.connect(
            lambda:self.stackedWidget.setCurrentWidget(self.view_reports)
        )

        self.manage_hospitals_button.clicked.connect(
            lambda:self.stackedWidget.setCurrentWidget(self.manage_hospitals)
        )

        self.manage_subscription_button.clicked.connect(
            lambda:self.stackedWidget.setCurrentWidget(self.manage_subscription)
        )

        self.logout_button.clicked.connect(self.logout)


    def show_page(self, page):
        self.stackedWidget.setCurrentWidget(page)

    def open_manage_users(self):
        self.show_page(self.manage_users)

        self.manage_user_stackedWidget.setCurrentWidget(self.user_list)
        self.manage_users_controller.load_users()


        