// 10年代经典的复古图形验证码库 - 纯前端 JS 实现，保障商城账户安全
var CaptchaGenerator = {
    currentCode: "",

    // 初始化并渲染验证码到指定的 canvas 元素上
    init: function(canvasId, inputId) {
        var self = this;
        var canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // 绑定点击事件，实现点击更换验证码
        $(canvas).off('click').on('click', function() {
            self.generate(canvas);
        });

        // 首次渲染
        self.generate(canvas);
    },

    // 生成随机颜色
    getRandomColor: function(min, max) {
        var r = Math.floor(Math.random() * (max - min) + min);
        var g = Math.floor(Math.random() * (max - min) + min);
        var b = Math.floor(Math.random() * (max - min) + min);
        return "rgb(" + r + "," + g + "," + b + ")";
    },

    // 核心绘制逻辑
    generate: function(canvas) {
        var ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // 随机字符池（排除易混淆的 0, o, 1, l, i 等）
        var chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789";
        var code = "";
        
        // 1. 绘制随机干扰线
        for (var i = 0; i < 4; i++) {
            ctx.strokeStyle = this.getRandomColor(120, 200);
            ctx.beginPath();
            ctx.moveTo(Math.random() * canvas.width, Math.random() * canvas.height);
            ctx.lineTo(Math.random() * canvas.width, Math.random() * canvas.height);
            ctx.stroke();
        }
        
        // 2. 绘制随机噪点
        for (var i = 0; i < 30; i++) {
            ctx.fillStyle = this.getRandomColor(150, 220);
            ctx.beginPath();
            ctx.arc(Math.random() * canvas.width, Math.random() * canvas.height, 1, 0, 2 * Math.PI);
            ctx.fill();
        }
        
        // 3. 绘制扭曲与旋转的验证码字符
        for (var i = 0; i < 4; i++) {
            var char = chars.charAt(Math.floor(Math.random() * chars.length));
            code += char;
            
            ctx.font = "bold 18px SimSun, Arial";
            ctx.fillStyle = this.getRandomColor(30, 100);
            
            ctx.save();
            var x = 10 + i * 22;
            var y = 20 + Math.random() * 5;
            var angle = (Math.random() - 0.5) * 0.4; // 扭曲偏转弧度
            ctx.translate(x, y);
            ctx.rotate(angle);
            ctx.fillText(char, 0, 0);
            ctx.restore();
        }
        
        this.currentCode = code;
    },

    // 校验输入值是否正确（忽略大小写）
    validate: function(inputValue) {
        return inputValue.trim().toLowerCase() === this.currentCode.toLowerCase();
    }
};
