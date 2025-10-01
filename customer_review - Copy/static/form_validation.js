document.addEventListener('DOMContentLoaded', () => {
    const initFormValidation = (formId) => {
        const form = document.getElementById(formId);
        if (!form) return;

        const inputs = form.querySelectorAll('input[data-validate]');
        
        form.addEventListener('submit', (event) => {
            let formIsValid = true;
            
            inputs.forEach(input => {
                const errorContainer = input.closest('.form-group').querySelector('.error-message');
                if (!errorContainer) return;

                if (input.value.trim() === '') {
                    formIsValid = false;
                    input.classList.add('input-error');
                    errorContainer.textContent = "This field is required."; // Set the error message
                } else {
                    input.classList.remove('input-error');
                    errorContainer.textContent = ""; // Clear the error message
                }
            });

            if (!formIsValid) {
                event.preventDefault(); // Stop submission
                const container = form.closest('.login-box');
                if (container) {
                    container.classList.add('shake-animation');
                    container.addEventListener('animationend', () => {
                        container.classList.remove('shake-animation');
                    }, { once: true });
                }
            }
        });

        // Remove error class and message as the user starts typing
        inputs.forEach(input => {
            input.addEventListener('input', () => {
                const errorContainer = input.closest('.form-group').querySelector('.error-message');
                if (input.classList.contains('input-error')) {
                    input.classList.remove('input-error');
                    if (errorContainer) {
                        errorContainer.textContent = "";
                    }
                }
            });
        });
    };

    initFormValidation('user-login-form');
    initFormValidation('admin-login-form');
});