from backend.fetches import get_all_users, get_all_roles, generate_employee_id, get_user
from backend.crud import save_user, delete_user, update_user as update_user_db
from PyQt6.QtWidgets import QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import QMessageBox
from datetime import date

class ManageUsers:
    def __init__(self, window):
        self.window = window

        self.window.search.textChanged.connect(self.filter_users)

        #NAVIGATION
        self.window.users_edit_button.clicked.connect(self.open_edit_user)
        self.window.users_create_button.clicked.connect(self.open_create_user)
        self.window.back_button.clicked.connect(self.open_user_list)
        self.window.edit_back_button.clicked.connect(self.open_user_list)

        self.window.edit_confirm_button.clicked.connect(
            self.update_user
        )

        self.window.confirm_button.clicked.connect(
            self.create_user
        )

        self.window.users_delete_button.clicked.connect(self.remove_user)
        

    #NAVIGATION
    def open_edit_user(self):
        table = self.window.users_table

        row = table.currentRow()

        if row == -1:
            QMessageBox.warning(
                self.window,
                "No User Selected",
                "Please select a user first."
            )
            return

        user_id = table.item(
            row,
            0
        ).data(Qt.ItemDataRole.UserRole)

        self.load_user_details(user_id)

        self.window.manage_user_stackedWidget.setCurrentWidget(
            self.window.edit_user
        )

    def open_create_user(self):
        self.load_roles()

        self.window.employee_id.setText(
            generate_employee_id()
        )
        self.window.employee_id.setReadOnly(True)

        self.window.manage_user_stackedWidget.setCurrentWidget(
            self.window.create_user
        )

    def open_user_list(self):
        self.clear_create_user_form()
        self.window.manage_user_stackedWidget.setCurrentWidget(
            self.window.user_list
        )


    #load_user function
    def load_users(self):
        users = get_all_users()

        # print(users)

        table = self.window.users_table

        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        table.setRowCount(len(users)) #set kung pila ka users


        #populate table
        for row, user in enumerate(users):
            item = QTableWidgetItem(user["user_fname"])
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Store the user_id in the table item
            item.setData(
                Qt.ItemDataRole.UserRole,
                user["user_id"]
            )

            table.setItem(row, 0, item)

            item = QTableWidgetItem(user["user_lname"])
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 1, item)

            item = QTableWidgetItem(user["roles"]["role_name"])
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 2, item)

            status = "Active" if user["is_active"] else "Inactive"
            item = QTableWidgetItem(status)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 3, item)

    #load roles function
    def load_roles(self):
        roles = get_all_roles()

        combo = self.window.role
        combo.clear()

        for role in roles:
            combo.addItem(
                role["role_name"],
                role["role_id"]
            )

    #filter_user function
    def filter_users(self):
        search_text = self.window.search.text().lower()

        table = self.window.users_table

        for row in range(table.rowCount()):
            show_row = False

            for col in range(table.columnCount()):
                item = table.item(row, col)

                if item and search_text in item.text().lower():
                    show_row = True
                    break

            table.setRowHidden(row, not show_row)

    def create_user(self):
        #account information
        email = self.window.email.text().strip()
        password = self.window.password.text()

        #personal details
        first_name = self.window.first_name.text()
        middle_name = self.window.middle_name.text()
        last_name = self.window.last_name.text()

        birth_date = self.window.birth_date.date().toPyDate()

        today = date.today()
        age = today.year - birth_date.year

        if(today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1

        print(age)


        #employment information
        employee_id = self.window.employee_id.text()
        role = self.window.role.currentText()
        role_id = self.window.role.currentData()

        #contact information
        contact_number = self.window.contact_number.text()
        home_address = self.window.address.text()

        errors = []

        if not email:
            errors.append("• Email is required.")

        if age < 21:
            errors.append("• Age is invalid to use system")

        if "@" not in email:
            errors.append("• Invalid Email")

        if not password:
            errors.append("• Password is required.")

        if not first_name:
            errors.append("• First name is required.")

        if not last_name:
            errors.append("• Last name is required.")

        if not employee_id:
            errors.append("• Employee ID is required.")

        if errors:
            QMessageBox.warning(
                self.window,
                "Please complete the form",
                "\n".join(errors)
            )
            return

        try:
            save_user(
                email=email,
                password=password,
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                birth_date=birth_date,
                employee_id=employee_id,
                role_id=role_id,
                contact_number=contact_number,
                address=home_address
            )

            QMessageBox.information(
                self.window,
                "Success",
                f"User '{first_name} {last_name}' was created successfully."
            )

            self.clear_create_user_form()
            self.load_users()

        except Exception as e:
            QMessageBox.critical(
                self.window,
                "Error",
                f"Failed to create user.\n\n{str(e)}"
            )

        print(email)
        print(password)
        print(first_name)
        print(middle_name)
        print(last_name)
        print(birth_date)
        print(employee_id)
        print(role)
        print(contact_number)
        print(home_address)

    def clear_create_user_form(self):
        # QLineEdits
        self.window.email.clear()
        self.window.password.clear()

        self.window.first_name.clear()
        self.window.middle_name.clear()
        self.window.last_name.clear()

        self.window.employee_id.clear()
        self.window.contact_number.clear()

        # QTextEdit
        self.window.address.clear()

        # QComboBox
        self.window.role.setCurrentIndex(0)

        # QDateEdit
        self.window.birth_date.setDate(QDate.currentDate())

    def remove_user(self):
        table = self.window.users_table

        row = table.currentRow()

        if row == -1:
            QMessageBox.warning(
                self.window,
                "No User Selected",
                "Please select a user first."
            )
            return

        first_name = table.item(row, 0).text()
        last_name = table.item(row, 1).text()

        user_id = table.item(
            row,
            0
        ).data(Qt.ItemDataRole.UserRole)

        reply = QMessageBox.question(
            self.window,
            "Delete User",
            f'Are you sure you want to delete "{first_name} {last_name}"?',
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_user(user_id)

            QMessageBox.information(
                self.window,
                "Success",
                f'"{first_name} {last_name}" has been deleted.'
            )

            self.load_users()

        except Exception as e:
            QMessageBox.critical(
                self.window,
                "Error",
                str(e)
            )

    def load_user_details(self, user_id):
        # Load roles into the edit combo box
        self.load_edit_roles()

        # Fetch user
        user = get_user(user_id)

        # Save selected user id for updating later
        self.selected_user_id = user_id

        # ----------------------------
        # Account Information
        # ----------------------------
        self.window.edit_email.setText(
            user["email"]
        )

        # Never display the current password
        self.window.edit_password.clear()
        self.window.edit_password.setPlaceholderText(
            "Leave blank to keep current password"
        )

        # ----------------------------
        # Personal Information
        # ----------------------------
        self.window.edit_first_name.setText(
            user["user_fname"] or ""
        )

        self.window.edit_middle_name.setText(
            user["user_mname"] or ""
        )

        self.window.edit_last_name.setText(
            user["user_lname"] or ""
        )

        if user["user_birthdate"]:
            birth = QDate.fromString(
                user["user_birthdate"],
                "yyyy-MM-dd"
            )

            self.window.edit_birth_date.setDate(birth)

        # ----------------------------
        # Employment Information
        # ----------------------------
        self.window.edit_employee_id.setText(
            user["employee_id"] or ""
        )

        self.window.edit_employee_id.setReadOnly(True)

        role_index = self.window.edit_role.findData(
            user["role_id"]
        )

        if role_index != -1:
            self.window.edit_role.setCurrentIndex(
                role_index
            )

        # ----------------------------
        # Contact Information
        # ----------------------------
        self.window.edit_contact_number.setText(
            user["user_contact_number"] or ""
        )

        self.window.edit_address.setText(
            user["user_address"] or ""
        )

    def load_edit_roles(self):
        roles = get_all_roles()

        combo = self.window.edit_role
        combo.clear()

        for role in roles:
            combo.addItem(
                role["role_name"],
                role["role_id"]
            )

    def update_user(self):
        # -----------------------------
        # Account Information
        # -----------------------------
        email = self.window.edit_email.text().strip()
        password = self.window.edit_password.text()

        # -----------------------------
        # Personal Information
        # -----------------------------
        first_name = self.window.edit_first_name.text()
        middle_name = self.window.edit_middle_name.text()
        last_name = self.window.edit_last_name.text()

        birth_date = (
            self.window.edit_birth_date
            .date()
            .toPyDate()
        )

        # -----------------------------
        # Employment Information
        # -----------------------------
        role_id = self.window.edit_role.currentData()

        # -----------------------------
        # Contact Information
        # -----------------------------
        contact_number = self.window.edit_contact_number.text()

        address = self.window.edit_address.text()

        # -----------------------------
        # Validation
        # -----------------------------
        errors = []

        if not email:
            errors.append("• Email is required.")

        if "@" not in email:
            errors.append("• Invalid email.")

        if not first_name:
            errors.append("• First name is required.")

        if not last_name:
            errors.append("• Last name is required.")

        if errors:
            QMessageBox.warning(
                self.window,
                "Validation Error",
                "\n".join(errors)
            )
            return

        # -----------------------------
        # Update Database
        # -----------------------------
        try:

            update_user_db(
                user_id=self.selected_user_id,
                email=email,
                password=password,
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                birth_date=birth_date,
                role_id=role_id,
                contact_number=contact_number,
                address=address
            )

            QMessageBox.information(
                self.window,
                "Success",
                "User updated successfully."
            )

            self.load_users()

            self.window.manage_user_stackedWidget.setCurrentWidget(
                self.window.user_list
            )

        except Exception as e:

            QMessageBox.critical(
                self.window,
                "Error",
                str(e)
            )