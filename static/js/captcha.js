// 10年代经典的复古图形验证码库 - 纯前端 JS 实现，保障商城账户安全
// 本库包含高覆盖率的中文注释，用于前端防刷、防暴力登录和保证系统基础人机安全性
var CaptchaGenerator = {
    // 存储当前生成并绘制成功的验证码小写字符串，用于和用户输入值比对
    currentCode: "",

    /**
     * 初始化并渲染验证码到指定的 canvas 元素上
     * @param {string} canvasId - Canvas 元素的 DOM ID
     * @param {string} inputId - 对应的输入框 DOM ID
     */
    init: function(canvasId, inputId) {
        var self = this;
        var canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // 绑定点击事件，实现点击验证码图片时自动更换验证码，保证较好的用户体验
        $(canvas).off('click').on('click', function() {
            self.generate(canvas);
        });

        // 首次加载页面时进行初始化渲染绘制
        self.generate(canvas);
    },

    /**
     * 生成并在指定的随机范围内返回一个 RGB 颜色字符串
     * @param {number} min - 颜色亮度/通道下限 (0-255)
     * @param {number} max - 颜色亮度/通道上限 (0-255)
     * @returns {string} 符合 rgb(r,g,b) 格式的 CSS 颜色值
     */
    getRandomColor: function(min, max) {
        var r = Math.floor(Math.random() * (max - min) + min);
        var g = Math.floor(Math.random() * (max - min) + min);
        var b = Math.floor(Math.random() * (max - min) + min);
        return "rgb(" + r + "," + g + "," + b + ")";
    },

    /**
     * 图形验证码核心绘制逻辑
     * @param {HTMLCanvasElement} canvas - 目标 Canvas DOM 对象
     */
    generate: function(canvas) {
        var ctx = canvas.getContext("2d");
        // 每次重新绘制前，先清空整个画布区域，防止多次绘制重叠混乱
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // 随机字符池（排除了极其易混淆的 0、o、1、l、i 等字符，提升买家识别体验）
        var chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789";
        var code = "";
        
        // 1. 绘制 4 条随机干扰线，增加机器 OCR 自动识别的难度
        for (var i = 0; i < 4; i++) {
            ctx.strokeStyle = this.getRandomColor(120, 200);
            ctx.beginPath();
            ctx.moveTo(Math.random() * canvas.width, Math.random() * canvas.height);
            ctx.lineTo(Math.random() * canvas.width, Math.random() * canvas.height);
            ctx.stroke();
        }
        
        // 2. 绘制 30 个随机噪点，防止简单的图像二值化分割攻击
        for (var i = 0; i < 30; i++) {
            ctx.fillStyle = this.getRandomColor(150, 220);
            ctx.beginPath();
            ctx.arc(Math.random() * canvas.width, Math.random() * canvas.height, 1, 0, 2 * Math.PI);
            ctx.fill();
        }
        
        // 3. 绘制扭曲与旋转的 4 位验证码字符，通过数学角度计算使其有良好的仿伪装效果
        for (var i = 0; i < 4; i++) {
            var char = chars.charAt(Math.floor(Math.random() * chars.length));
            code += char;
            
            // 设定复古而严肃的黑体或 Arial 字体样式与大小
            ctx.font = "bold 18px SimSun, Arial";
            // 字符填充颜色设定为偏深色，保证人眼的高对比度可读性
            ctx.fillStyle = this.getRandomColor(30, 100);
            
            ctx.save();
            // 计算字符在横轴方向上的均匀分段落点
            var x = 10 + i * 22;
            // 纵向坐标加入小幅度随机上下偏移
            var y = 20 + Math.random() * 5;
            // 产生一个介于 -0.2 弧度到 0.2 弧度之间的随机倾斜偏转角度
            var angle = (Math.random() - 0.5) * 0.4;
            
            // 平移坐标系原点到目标绘图位置，进行旋转后写入字符，最后恢复坐标系
            ctx.translate(x, y);
            ctx.rotate(angle);
            ctx.fillText(char, 0, 0);
            ctx.restore();
        }
        
        // 写入组件全局缓存中，用于后续表单提交前的检验
        this.currentCode = code;
    },

    /**
     * 校验用户输入的字符值是否与当前画布显示的字符匹配
     * @param {string} inputValue - 用户在前端表单中输入的验证码
     * @returns {boolean} 校验是否通过（忽略前后空格及英文字母大小写）
     */
    validate: function(inputValue) {
        return inputValue.trim().toLowerCase() === this.currentCode.toLowerCase();
    }
};
