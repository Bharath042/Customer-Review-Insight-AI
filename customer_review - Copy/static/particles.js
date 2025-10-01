document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('particle-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    let width, height;
    let particles = [];
    const particleCount = 20;

    function resizeCanvas() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    class Particle {
        constructor() {
            this.x = Math.random() * width;
            // CORRECTED LINE: Particles now start everywhere on the screen
            this.y = Math.random() * height; 
            this.vx = (Math.random() - 0.5) * 0.1;
            this.vy = -(Math.random() * 0.3 + 0.2); // Still move upwards
            this.width = Math.random() * 150 + 80;
            this.height = Math.random() * 50 + 40;
            this.opacity = Math.random() * 0.1 + 0.05;
        }

        update() {
            this.x += this.vx;
            this.y += this.vy;

            // Reset when it goes off screen to the top, and reappear at the bottom
            if (this.y < -this.height) {
                this.y = height;
                this.x = Math.random() * width;
            }
            if (this.x < -this.width || this.x > width) {
                this.x = Math.random() * width;
            }
        }

        draw() {
            ctx.fillStyle = `rgba(48, 54, 61, ${this.opacity})`;
            ctx.strokeStyle = `rgba(139, 148, 158, ${this.opacity * 1})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.roundRect(this.x, this.y, this.width, this.height, [8]);
            ctx.fill();
            ctx.stroke();

            ctx.fillStyle = `rgba(139, 148, 158, ${this.opacity * 1.5})`;
            ctx.fillRect(this.x + 10, this.y + 10, this.width * 0.7, 4);
            ctx.fillRect(this.x + 10, this.y + 20, this.width * 0.5, 4);
        }
    }

    function init() {
        particles = []; // Clear existing particles on resize/init
        for (let i = 0; i < particleCount; i++) {
            particles.push(new Particle());
        }
    }

    function animate() {
        ctx.clearRect(0, 0, width, height);
        particles.forEach(p => {
            p.update();
            p.draw();
        });
        requestAnimationFrame(animate);
    }

    // Re-initialize particles on resize to prevent clumping
    window.addEventListener('resize', () => {
        resizeCanvas();
        init();
    });

    init();
    animate();
});