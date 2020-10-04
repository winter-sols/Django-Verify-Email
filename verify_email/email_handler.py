"""
This is the core module for:
    1. Generating unique hashed Token for each user.
    2. Generate a link for confirmation from client's side by /...<encoded email>/<encoded token>/.
    3. Set the new user as inactive and saves it.
    4. Send an email to user with specified template containing the link.
    5. Verifies the link and token.
    6. Destroy token and set the user's "is_active" status as True and "last_login" as timezone.now()

The module contains private classes and method (starting with "_" or "__") which aren't suppose to be used outside.

Only two global functions are supposed to be used outside of this module as they provide a wrap for making object and 
calling method with params to reduce one level of extra code.
"""

from django.core.mail import BadHeaderError, send_mail
from django.contrib.sites.shortcuts import get_current_site
from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as base64error
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from smtplib import SMTPException
from .app_configurations import GetFieldFromSettings
from binascii import Error as bs64
from django.shortcuts import render, redirect, HttpResponse
from django.contrib import messages
from django.urls import reverse

success_redirect = GetFieldFromSettings().get('verification_success_redirect')
failed_redirect = GetFieldFromSettings().get('verification_failed_redirect')

success_msg = GetFieldFromSettings().get('verification_success_msg')
failed_msg = GetFieldFromSettings().get('verification_failed_msg')

failed_template = GetFieldFromSettings().get('verification_failed_template')
success_template = GetFieldFromSettings().get('verification_success_template')

class _VerifyEmail:
    """
    This class does four things:
    1. creates tokens for each user.
    2. set each user as inactive and saves it
    3. embed encoded token with encoded email to make verification link.
    4. sends the email to user with that link.
    """

    def __init__(self):
        self.settings = GetFieldFromSettings()

    def __get_hashed_token(self, user):
        return urlsafe_b64encode(str(default_token_generator.make_token(user)).encode('utf-8')).decode('utf-8')


    def __make_verification_url(self, current_site, inactive_user, useremail):
        token = self.__get_hashed_token(inactive_user)
        email_enc = urlsafe_b64encode(str(useremail).encode('utf-8')).decode('utf-8')
        link = f"{current_site}/verification/user/verify-email/{email_enc}/{token}/"

        return link
    
    def send_verification_link(self, request, form):
        try:
            inactive_user = form.save(commit=False)
            inactive_user.is_active = False
            inactive_user.save()
            current_site = get_current_site(request)
            try:
                useremail = form.cleaned_data[self.settings.get('email_field_name')]
            except:
                raise KeyError(
            'No key named "email" in your form. Your field should be named as email in form OR set a variable "EMAIL_FIELD_NAME" with the name of current field in settings.py if you want to use current name as email field.'
            )

            verification_url = self.__make_verification_url(current_site, inactive_user, useremail)
            subject = self.settings.get('subject')
            msg = render_to_string(self.settings.get('html_message_template', raise_exception=True), {"link": verification_url})

            try:
                send_mail(subject, strip_tags(msg), from_email=self.settings.get('from_alias'), recipient_list=[useremail], html_message=msg)
                return True
            except (BadHeaderError, SMTPException):
                inactive_user.delete()
                return False

        except Exception as error:
            inactive_user.delete()
            if self.settings.get('debug_settings', raise_exception=True):
                raise Exception(error)


class _UserActivationProcess:
    """
    This class is pretty self.explanatory...
    """

    def __init__(self):
        pass

    def __activate_user(self,user):
        user.is_active = True
        user.last_login = timezone.now()
        user.save()
        
    def verify_token(self,useremail, usertoken):
        try:
            email = urlsafe_b64decode(useremail).decode('utf-8')
            token = urlsafe_b64decode(usertoken).decode('utf-8')
        except bs64:
            return False

        inactive_unique_user = get_user_model().objects.get(email=email)
        try:
            valid  = default_token_generator.check_token(inactive_unique_user, token)
            if valid:
                self.__activate_user(inactive_unique_user)
                return valid
            else:
                return False
        except:
            return False


#  These two methods are supposed to be called
def send_verification_email(request, form):
    return _VerifyEmail().send_verification_link(request, form)

def varify_user(useremail, usertoken):
    return _UserActivationProcess().verify_token(useremail, usertoken)

def verify_user_and_activate(request, useremail, usertoken):
    """
    verify the user's email and token and redirect'em accordingly.
    """
    
    if varify_user(useremail, usertoken):
        if success_redirect and not success_template:
            messages.SUCCESS(request, 'Successfully Verified!')
            return redirect(to=success_redirect)
        return render(
            request,
            template_name=success_template,
            context={
                'msg': success_msg,
                'status':'Verification Successfull!',
                'link': reverse(success_redirect)
            }
        )
    else:
        return render(
            request,
            template_name=failed_template, 
            context={
                'msg': failed_msg,
                'status':'Verification Failed!',
            }
        )





