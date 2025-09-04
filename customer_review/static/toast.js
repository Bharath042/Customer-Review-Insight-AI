document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.toast');
    
    alerts.forEach((alert, index) => {
        // Stagger the dismissal time slightly for multiple messages
        const duration = 3000 + (index * 500); 

        setTimeout(() => {
            alert.classList.add('fade-out');
            // Remove the element from the DOM after the animation completes
            alert.addEventListener('animationend', () => {
                alert.remove();
            });
        }, duration);
    });
});