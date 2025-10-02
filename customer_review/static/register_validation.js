document.addEventListener('DOMContentLoaded', () => {
    // --- Get all the form elements ---
    const emailInput = document.getElementById('email');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirm-password');
    const submitButton = document.getElementById('submit-btn');
    const popover = document.getElementById('password-popover');

    // Error message containers
    const emailError = document.getElementById('email-error');
    const usernameError = document.getElementById('username-error');
    const matchError = document.getElementById('match-error');

    // Password strength rules
    const lengthRule = document.getElementById('length');
    const uppercaseRule = document.getElementById('uppercase');
    const numberRule = document.getElementById('number');
    const specialRule = document.getElementById('special');

    const allInputs = [emailInput, usernameInput, passwordInput, confirmPasswordInput];
    const passwordRules = [lengthRule, uppercaseRule, numberRule, specialRule];

    // --- Utility Functions ---
    const setFieldState = (field, errorContainer, message, isValid) => {
        if (isValid) {
            field.classList.remove('invalid');
            field.classList.add('valid');
            errorContainer.style.display = 'none';
        } else {
            field.classList.remove('valid');
            field.classList.add('invalid');
            errorContainer.textContent = message;
            errorContainer.style.display = 'block';
        }
        checkFormValidity();
    };

    const updatePasswordRule = (element, isValid) => {
        element.classList.toggle('valid', isValid);
        element.classList.toggle('invalid', !isValid);
    };

    // --- Validation Logic ---
    const validateEmail = () => {
        const email = emailInput.value;
        const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        if (email === "") {
            setFieldState(emailInput, emailError, "Email is required.", false);
        } else if (!emailRegex.test(email)) {
            setFieldState(emailInput, emailError, "Please enter a valid email address.", false);
        } else {
            setFieldState(emailInput, emailError, "", true);
        }
    };

    const validateUsername = () => {
        const username = usernameInput.value;
        if (username.length < 3) {
            setFieldState(usernameInput, usernameError, "Username must be at least 3 characters long.", false);
        } else {
            setFieldState(usernameInput, usernameError, "", true);
        }
    };

    const validatePassword = () => {
        const password = passwordInput.value;
        const isLengthValid = password.length >= 8;
        const isUppercaseValid = /[A-Z]/.test(password);
        const isNumberValid = /[0-9]/.test(password);
        const isSpecialValid = /[!@#$%^&*(),.?":{}|<>]/.test(password);

        updatePasswordRule(lengthRule, isLengthValid);
        updatePasswordRule(uppercaseRule, isUppercaseValid);
        updatePasswordRule(numberRule, isNumberValid);
        updatePasswordRule(specialRule, isSpecialValid);

        const isPasswordStrong = isLengthValid && isUppercaseValid && isNumberValid && isSpecialValid;
        if (isPasswordStrong) {
            passwordInput.classList.remove('invalid');
            passwordInput.classList.add('valid');
        } else {
            passwordInput.classList.remove('valid');
        }
        
        validateConfirmPassword();
    };

    const validateConfirmPassword = () => {
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        const isPasswordStrong = passwordRules.every(rule => rule.classList.contains('valid'));

        if (confirmPassword === "" && password.length > 0) {
            setFieldState(confirmPasswordInput, matchError, "Please confirm your password.", false);
        } else if (password !== confirmPassword) {
            setFieldState(confirmPasswordInput, matchError, "Passwords do not match.", false);
        } else if (password.length > 0 && isPasswordStrong) {
            setFieldState(confirmPasswordInput, matchError, "", true);
        } else {
            confirmPasswordInput.classList.remove('valid', 'invalid');
            matchError.style.display = 'none';
        }
    };

    // --- Check overall form validity ---
    const checkFormValidity = () => {
        const isEmailValid = emailInput.classList.contains('valid');
        const isUsernameValid = usernameInput.classList.contains('valid');
        const isPasswordStrong = passwordRules.every(rule => rule.classList.contains('valid'));
        const doPasswordsMatch = confirmPasswordInput.classList.contains('valid');
        
        submitButton.disabled = !(isEmailValid && isUsernameValid && isPasswordStrong && doPasswordsMatch);
    };

    // --- Attach Event Listeners ---
    emailInput.addEventListener('input', validateEmail);
    usernameInput.addEventListener('input', validateUsername);
    passwordInput.addEventListener('input', validatePassword);
    confirmPasswordInput.addEventListener('input', validateConfirmPassword);
    
    passwordInput.addEventListener('focus', () => popover.classList.add('visible'));
    passwordInput.addEventListener('blur', () => popover.classList.remove('visible'));

    // --- Password Visibility Toggle ---
    document.querySelectorAll('.toggle-password').forEach(toggle => {
        toggle.addEventListener('click', () => {
            const passwordField = toggle.closest('.password-wrapper').querySelector('input');
            const eyeIcon = toggle.querySelector('.eye-icon');
            const eyeSlashIcon = toggle.querySelector('.eye-slash-icon');
            if (passwordField.type === 'password') {
                passwordField.type = 'text';
                if (eyeIcon) eyeIcon.style.display = 'none';
                if (eyeSlashIcon) eyeSlashIcon.style.display = 'block';
            } else {
                passwordField.type = 'password';
                if (eyeIcon) eyeIcon.style.display = 'block';
                if (eyeSlashIcon) eyeSlashIcon.style.display = 'none';
            }
        });
    });
});