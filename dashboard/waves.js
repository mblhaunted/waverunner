/**
 * Alien Cosmos - Canvas animation for M83-style alien vibes background
 *
 * Renders:
 * - Starfield with twinkling stars
 * - Alien perspective grid with purple/pink glow
 * - Cosmic particle effects flowing through space
 */

class WaveParticles {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.stars = [];
        this.gridOffset = 0;

        this.resizeCanvas();
        this.initStars();
        window.addEventListener('resize', () => {
            this.resizeCanvas();
            this.initStars();
        });

        this.animate();
    }

    initStars() {
        this.stars = [];
        const starCount = 200;
        for (let i = 0; i < starCount; i++) {
            this.stars.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                radius: Math.random() * 1.5,
                alpha: Math.random(),
                twinkleSpeed: 0.02 + Math.random() * 0.03,
                color: Math.random() > 0.7 ? '#8b5cf6' : '#f0f9ff'
            });
        }
    }

    resizeCanvas() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    drawStars() {
        const ctx = this.ctx;
        this.stars.forEach(star => {
            // Twinkle animation
            star.alpha += star.twinkleSpeed;
            if (star.alpha > 1 || star.alpha < 0.2) {
                star.twinkleSpeed *= -1;
            }

            ctx.fillStyle = star.color;
            ctx.globalAlpha = star.alpha;
            ctx.shadowBlur = 10;
            ctx.shadowColor = star.color;
            ctx.beginPath();
            ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
            ctx.fill();
        });
        ctx.shadowBlur = 0;
        ctx.globalAlpha = 1;
    }

    drawGrid() {
        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;

        // Horizontal lines (perspective, moving) - purple/pink alien grid
        const horizonY = height / 2;
        for (let y = horizonY; y < height; y += 30) {
            const relativeY = (y - horizonY + this.gridOffset) % 30;
            const actualY = horizonY + relativeY + Math.floor((y - horizonY) / 30) * 30;
            if (actualY < height) {
                const alpha = Math.min(0.2, (actualY - horizonY) / height * 0.3);
                const progress = (actualY - horizonY) / (height - horizonY);
                // Gradient from purple to pink
                const r = Math.round(139 + (236 - 139) * progress);
                const g = Math.round(92 + (72 - 92) * progress);
                const b = Math.round(246 + (153 - 246) * progress);
                ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
                ctx.shadowBlur = 3;
                ctx.shadowColor = `rgba(${r}, ${g}, ${b}, 0.5)`;
                ctx.beginPath();
                ctx.moveTo(0, actualY);
                ctx.lineTo(width, actualY);
                ctx.stroke();
            }
        }

        // Vertical lines (converging to center) - alien perspective
        const vanishingX = width / 2;
        const vanishingY = horizonY;

        for (let x = 0; x <= width; x += 50) {
            const alpha = 0.12 - Math.abs(x - vanishingX) / width * 0.08;
            const lateralProgress = Math.abs(x - vanishingX) / (width / 2);
            // Gradient based on distance from center
            const r = Math.round(139 + (59 - 139) * lateralProgress);
            const g = Math.round(92 + (130 - 92) * lateralProgress);
            const b = Math.round(246);
            ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
            ctx.shadowBlur = 2;
            ctx.shadowColor = `rgba(${r}, ${g}, ${b}, 0.3)`;
            ctx.beginPath();
            ctx.moveTo(x, height);
            const topX = vanishingX + (x - vanishingX) * 0.3;
            ctx.lineTo(topX, vanishingY);
            ctx.stroke();
        }
        ctx.shadowBlur = 0;
    }

    addWaveParticle(fromX, fromY, toX, toY) {
        // Create glowing particle that flows along edge
        this.particles.push({
            x: fromX,
            y: fromY,
            targetX: toX,
            targetY: toY,
            progress: 0,
            color: this.getGradientColor(Math.random()),
            size: 3 + Math.random() * 3
        });
    }

    getGradientColor(t) {
        // Purple → Pink → Blue cosmic gradient
        if (t < 0.5) {
            return this.lerpColor('#8b5cf6', '#ec4899', t * 2);
        } else {
            return this.lerpColor('#ec4899', '#3b82f6', (t - 0.5) * 2);
        }
    }

    lerpColor(color1, color2, t) {
        const c1 = parseInt(color1.slice(1), 16);
        const c2 = parseInt(color2.slice(1), 16);

        const r1 = (c1 >> 16) & 0xff;
        const g1 = (c1 >> 8) & 0xff;
        const b1 = c1 & 0xff;

        const r2 = (c2 >> 16) & 0xff;
        const g2 = (c2 >> 8) & 0xff;
        const b2 = c2 & 0xff;

        const r = Math.round(r1 + (r2 - r1) * t);
        const g = Math.round(g1 + (g2 - g1) * t);
        const b = Math.round(b1 + (b2 - b1) * t);

        return `rgb(${r}, ${g}, ${b})`;
    }

    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw starfield first (background layer)
        this.drawStars();

        // Animate alien grid movement (slower, more dreamlike)
        this.gridOffset = (this.gridOffset + 0.3) % 30;
        this.drawGrid();

        // Update and draw particles
        this.particles = this.particles.filter(p => {
            p.progress += 0.02;
            if (p.progress > 1) return false;

            const x = p.x + (p.targetX - p.x) * p.progress;
            const y = p.y + (p.targetY - p.y) * p.progress;

            // Draw glowing cosmic particle with enhanced trail
            const alpha = 1 - p.progress * 0.3;
            this.ctx.fillStyle = p.color;
            this.ctx.shadowBlur = 30;
            this.ctx.shadowColor = p.color;
            this.ctx.globalAlpha = alpha;
            this.ctx.beginPath();
            this.ctx.arc(x, y, p.size, 0, Math.PI * 2);
            this.ctx.fill();

            // Enhanced trail effect (more M83-style glow)
            if (p.progress > 0.1) {
                const trailX = p.x + (p.targetX - p.x) * (p.progress - 0.1);
                const trailY = p.y + (p.targetY - p.y) * (p.progress - 0.1);
                this.ctx.globalAlpha = alpha * 0.6;
                this.ctx.shadowBlur = 20;
                this.ctx.beginPath();
                this.ctx.arc(trailX, trailY, p.size * 0.6, 0, Math.PI * 2);
                this.ctx.fill();
            }

            // Second trail layer for extra glow
            if (p.progress > 0.2) {
                const trail2X = p.x + (p.targetX - p.x) * (p.progress - 0.2);
                const trail2Y = p.y + (p.targetY - p.y) * (p.progress - 0.2);
                this.ctx.globalAlpha = alpha * 0.3;
                this.ctx.shadowBlur = 15;
                this.ctx.beginPath();
                this.ctx.arc(trail2X, trail2Y, p.size * 0.4, 0, Math.PI * 2);
                this.ctx.fill();
            }

            this.ctx.shadowBlur = 0;
            this.ctx.globalAlpha = 1;

            return true;
        });

        requestAnimationFrame(() => this.animate());
    }
}

// Initialize wave particles on load
let waveParticles;
document.addEventListener('DOMContentLoaded', () => {
    waveParticles = new WaveParticles('grid-bg');
});
