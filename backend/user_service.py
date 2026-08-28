from backend.supabase_client import supabase_admin

def create_user(
        email,
        temporary_password,
        employee_id,
        first_name,
        middle_name,
        last_name,
        birthdate,
        sex,
        contact_number,
        address,
        department,
        job_title,
        role_id
):
    auth_user = None

    try:
        auth_response = (
            supabase_admin.auth.admin.create_user(
                {
                    "email": email,
                    "password": temporary_password,
                    "email_confirm": True
                }
            )
        )

        auth_user = auth_response.user

        if not auth_user:
            raise RuntimeError(
                "Failed to create user in Supabase Auth."
            )

        user_id = auth_user.id

        profile_data = {
            "user_id": user_id,
            "employee_id": employee_id,
            "user_fname": first_name,
            "user_mname": middle_name,
            "user_lname": last_name,
            "user_birthdate": birthdate.isoformat() if birthdate else None,
            "user_sex": sex,
            "user_contact_number": contact_number,
            "user_address": address,
            "user_department": department,
            "user_job_title": job_title,
            "role_id": role_id,
            "is_active": True
        }

        profile_response = (
            supabase_admin
            .table("user_profiles")
            .insert(profile_data)
            .execute()
        )

        return {
            "success": True,
            "user_id": user_id,
            "email": email,
            "data": profile_response.data
        }

    except Exception as e:
        if auth_user:
            try:
                supabase_admin.auth.admin.delete_user(auth_user.id)
            except Exception as delete_error:
                print(
                    "Failed to rollback Auth user:",
                    delete_error
                )

        return {
            "success": False,
            "message": str(e)
        }

def delete_user(user_id):

    try:

        # ==========================================
        # DELETE USER PROFILE
        # ==========================================

        supabase_admin.table(
            "user_profiles"
        ).delete().eq(
            "user_id",
            user_id
        ).execute()


        # ==========================================
        # DELETE SUPABASE AUTH USER
        # ==========================================

        supabase_admin.auth.admin.delete_user(
            user_id
        )


        return {

            "success": True

        }


    except Exception as e:

        return {

            "success": False,

            "message": str(e)

        }

print(
    "USER SERVICE IMPORTED",
    supabase_admin
)