// 创建背景动画
function createBubbles() {
  const container = document.getElementById("bubbleContainer");
  const bubbleCount = 15;

  for (let i = 0; i < bubbleCount; i++) {
    const bubble = document.createElement("div");
    bubble.classList.add("bubble");

    // 随机大小
    const size = Math.random() * 100 + 20;
    bubble.style.width = `${size}px`;
    bubble.style.height = `${size}px`;

    // 随机位置
    bubble.style.left = `${Math.random() * 100}%`;

    // 随机动画延迟
    bubble.style.animationDelay = `${Math.random() * 5}s`;

    container.appendChild(bubble);
  }
}

// 密码显示/隐藏切换
document
  .getElementById("togglePassword")
  .addEventListener("click", function () {
    const passwordInput = document.getElementById("password");
    if (passwordInput.type === "password") {
      passwordInput.type = "text";
      this.classList.remove("fa-eye");
      this.classList.add("fa-eye-slash");
    } else {
      passwordInput.type = "password";
      this.classList.remove("fa-eye-slash");
      this.classList.add("fa-eye");
    }
  });

document
  .getElementById("toggleRegisterPassword")
  .addEventListener("click", function () {
    const passwordInput = document.getElementById("registerPassword");
    if (passwordInput.type === "password") {
      passwordInput.type = "text";
      this.classList.remove("fa-eye");
      this.classList.add("fa-eye-slash");
    } else {
      passwordInput.type = "password";
      this.classList.remove("fa-eye-slash");
      this.classList.add("fa-eye");
    }
  });

// 显示注册模态框
document.getElementById("showRegister").addEventListener("click", function (e) {
  e.preventDefault();
  const registerModal = new bootstrap.Modal(
    document.getElementById("registerModal")
  );
  registerModal.show();
});

// 生成随机验证码
function generateCaptcha() {
  const chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  let captcha = "";
  for (let i = 0; i < 4; i++) {
    captcha += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return captcha;
}

// 刷新验证码
function refreshCaptcha() {
  const captcha = generateCaptcha();
  document.getElementById("captchaImage").textContent = captcha;
  return captcha;
}

// 当前验证码
let currentCaptcha = refreshCaptcha();
// 添加注册表单提交处理（在 login.js 末尾添加）
document
  .getElementById("registerForm")
  .addEventListener("submit", async function (e) {
    e.preventDefault();

    // 获取表单数据
    const username = document.getElementById("registerUsername").value;
    const email = document.getElementById("registerEmail").value;
    const password = document.getElementById("registerPassword").value;
    const confirmPassword = document.getElementById(
      "registerConfirmPassword"
    ).value;

    // 验证密码一致性
    if (password !== confirmPassword) {
      alert("两次输入的密码不一致");
      return;
    }

    try {
      // 发送注册请求
      const response = await fetch("/api/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password }),
      });

      const data = await response.json();

      if (data.success) {
        alert("注册成功！现在可以登录");

        // 关闭模态框
        const registerModal = bootstrap.Modal.getInstance(
          document.getElementById("registerModal")
        );
        registerModal.hide();

        // 清空表单
        this.reset();
      } else {
        alert("注册失败: " + data.message);
      }
    } catch (error) {
      console.error("注册请求失败:", error);
      alert("服务器错误，请重试");
    }
  });

document
  .getElementById("loginForm")
  .addEventListener("submit", async function (e) {
    e.preventDefault();

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    const captcha = document.getElementById("captcha").value;
    const rememberMe = document.getElementById("rememberMe").checked;

    // 简单验证
    let isValid = true;

    if (username.trim() === "") {
      document.getElementById("usernameError").style.display = "block";
      isValid = false;
    } else {
      document.getElementById("usernameError").style.display = "none";
    }

    if (password.length < 6) {
      document.getElementById("passwordError").style.display = "block";
      isValid = false;
    } else {
      document.getElementById("passwordError").style.display = "none";
    }

    // 验证码校验
    if (captcha.toUpperCase() !== currentCaptcha) {
      document.getElementById("captchaError").style.display = "block";
      isValid = false;
    } else {
      document.getElementById("captchaError").style.display = "none";
    }

    if (!isValid) {
      currentCaptcha = refreshCaptcha();
      return;
    }

    try {
      // 发送登录请求
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (data.success) {
        const successMessage = document.getElementById("successMessage");
        successMessage.style.display = "block";

        // 清除所有旧的偏好设置
        localStorage.removeItem("userPreferences");
        sessionStorage.removeItem("userPreferences");

        // 清除旧的登录状态
        localStorage.removeItem("isLoggedIn");
        sessionStorage.removeItem("isLoggedIn");

        // 保存登录状态
        if (rememberMe) {
          localStorage.setItem("isLoggedIn", "true");
          localStorage.setItem("username", username);
        } else {
          sessionStorage.setItem("isLoggedIn", "true");
          sessionStorage.setItem("username", username);
        }

        // 初始化偏好设置有效标志
        let hasValidPreferences = false;

        // 检查偏好设置是否有效
        if (
          data.preferences !== null &&
          data.preferences !== "null" &&
          data.preferences !== "" &&
          data.preferences !== "[]"
        ) {
          try {
            const prefs = JSON.parse(data.preferences);
            if (Array.isArray(prefs) && prefs.length > 0) {
              hasValidPreferences = true;

              // 保存到本地存储
              if (rememberMe) {
                localStorage.setItem("userPreferences", data.preferences);
              } else {
                sessionStorage.setItem("userPreferences", data.preferences);
              }
            }
          } catch (e) {
            console.error("偏好设置解析失败", e);
          }
        }

        // 根据实际偏好状态跳转
        const redirectPage = hasValidPreferences
          ? "index.html"
          : "genre_selection.html";

        // 2秒后跳转
        setTimeout(() => {
          console.log("跳转到:", redirectPage);
          window.location.href = redirectPage;
        }, 2000);
      } else {
        document.getElementById("passwordError").textContent =
          data.message || "登录失败";
        document.getElementById("passwordError").style.display = "block";
        currentCaptcha = refreshCaptcha();
      }
    } catch (error) {
      console.error("登录请求失败:", error);
      document.getElementById("passwordError").textContent = "服务器错误";
      document.getElementById("passwordError").style.display = "block";
      currentCaptcha = refreshCaptcha();
    }
  });
// 初始化
document.addEventListener("DOMContentLoaded", function () {
  createBubbles();

  // 如果有记住的用户名，填充表单
  const savedUsername =
    localStorage.getItem("username") ||
    sessionStorage.getItem("username") ||
    "";

  if (savedUsername) {
    document.getElementById("username").value = savedUsername;
    document.getElementById("rememberMe").checked = true;
  }
});
