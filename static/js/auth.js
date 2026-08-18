// AI 导诊系统 - 认证模块 JavaScript

// ========== 认证状态管理 ==========

class AuthManager {
    constructor() {
        this.user = null;
        this.isAdmin = false;
        this.init();
    }

    /**
     * 初始化认证状态
     */
    async init() {
        try {
            const response = await fetch('/api/user/status');
            const data = await response.json();

            if (data.logged_in) {
                this.user = {
                    username: data.username
                };
                this.isAdmin = data.username && data.username.startsWith('admin');
            }
        } catch (error) {
            console.error('获取认证状态失败:', error);
        }
    }

    /**
     * 检查是否已登录
     */
    isLoggedIn() {
        return this.user !== null;
    }

    /**
     * 检查是否为管理员
     */
    isAdminUser() {
        return this.isAdmin;
    }

    /**
     * 获取当前用户
     */
    getCurrentUser() {
        return this.user;
    }

    /**
     * 用户登录
     */
    async login(username, password) {
        try {
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);

            const response = await fetch('/user/login', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('登录失败');
            }

            const html = await response.text();

            // 检查是否包含错误信息
            if (html.includes('error') || html.includes('用户名或密码错误')) {
                return { success: false, error: '用户名或密码错误' };
            }

            // 登录成功
            await this.init();
            return { success: true };
        } catch (error) {
            console.error('登录失败:', error);
            return { success: false, error: error.message || '登录失败' };
        }
    }

    /**
     * 用户注册
     */
    async register(username, password, password2) {
        try {
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);
            formData.append('password2', password2);

            const response = await fetch('/user/register', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('注册失败');
            }

            const html = await response.text();

            // 检查是否包含错误信息
            if (html.includes('error')) {
                const errorMatch = html.match(/error["']?\s*[:=]\s*["']([^"']+)["']/);
                if (errorMatch) {
                    return { success: false, error: errorMatch[1] };
                }
                return { success: false, error: '注册失败' };
            }

            // 检查是否成功
            if (html.includes('注册成功')) {
                return { success: true };
            }

            return { success: false, error: '注册失败' };
        } catch (error) {
            console.error('注册失败:', error);
            return { success: false, error: error.message || '注册失败' };
        }
    }

    /**
     * 管理员登录
     */
    async adminLogin(username, password, loginType = 'password', smsCode = '') {
        try {
            const formData = new FormData();
            formData.append('username', username);

            if (loginType === 'sms') {
                formData.append('sms_code', smsCode);
            } else {
                formData.append('password', password);
            }

            const response = await fetch('/admin/login', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('登录失败');
            }

            // 重定向到管理后台
            if (response.redirected) {
                await this.init();
                return { success: true, redirect: response.url };
            }

            return { success: false, error: '登录失败' };
        } catch (error) {
            console.error('管理员登录失败:', error);
            return { success: false, error: error.message || '登录失败' };
        }
    }

    /**
     * 管理员注册
     */
    async adminRegister(username, password, phone, smsCode) {
        try {
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);
            formData.append('phone', phone);
            formData.append('sms_code', smsCode);

            const response = await fetch('/admin/register', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('注册失败');
            }

            const html = await response.text();

            // 检查是否包含错误信息
            if (html.includes('error')) {
                const errorMatch = html.match(/error["']?\s*[:=]\s*["']([^"']+)["']/);
                if (errorMatch) {
                    return { success: false, error: errorMatch[1] };
                }
                return { success: false, error: '注册失败' };
            }

            // 检查是否成功
            if (html.includes('注册成功')) {
                return { success: true };
            }

            return { success: false, error: '注册失败' };
        } catch (error) {
            console.error('管理员注册失败:', error);
            return { success: false, error: error.message || '注册失败' };
        }
    }

    /**
     * 发送短信验证码
     */
    async sendSMSCode(phone) {
        try {
            const response = await fetch('/api/admin/send_sms', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ phone })
            });

            const data = await response.json();

            if (!data.success) {
                return { success: false, error: data.error || '发送失败' };
            }

            return { success: true, code: data.dev_code };
        } catch (error) {
            console.error('发送验证码失败:', error);
            return { success: false, error: '发送失败' };
        }
    }

    /**
     * 退出登录
     */
    async logout() {
        try {
            await fetch('/user/logout', { method: 'POST' });
            await fetch('/admin/logout', { method: 'POST' });

            this.user = null;
            this.isAdmin = false;

            // 重定向到首页
            window.location.href = '/';
        } catch (error) {
            console.error('退出登录失败:', error);
            // 即使失败也重定向
            window.location.href = '/';
        }
    }

    /**
     * 检查用户名是否可用
     */
    async checkUsernameAvailability(username) {
        try {
            const response = await fetch('/api/admin/check_username', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username })
            });

            const data = await response.json();
            return data.available !== false;
        } catch (error) {
            console.error('检查用户名失败:', error);
            return false;
        }
    }
}

// ========== 全局认证管理器 ==========

const auth = new AuthManager();

// ========== 认证 UI 组件 ==========

/**
 * 切换登录类型（密码/短信）
 */
function switchLoginType(type) {
    const passwordGroup = document.getElementById('passwordGroup');
    const smsGroup = document.getElementById('smsGroup');
    const typeRadios = document.querySelectorAll('input[name="login_type"]');

    typeRadios.forEach(radio => {
        radio.checked = (radio.value === type);
    });

    if (type === 'sms') {
        passwordGroup.style.display = 'none';
        smsGroup.style.display = 'block';
    } else {
        passwordGroup.style.display = 'block';
        smsGroup.style.display = 'none';
    }
}

/**
 * 切换注册类型（用户/管理员）
 */
function switchRegisterRole(role) {
    const tabUser = document.getElementById('tabUser');
    const tabAdmin = document.getElementById('tabAdmin');
    const formUser = document.getElementById('formUser');
    const formAdmin = document.getElementById('formAdmin');

    if (role === 'user') {
        tabUser.classList.add('active');
        tabAdmin.classList.remove('active');
        formUser.style.display = 'block';
        formAdmin.style.display = 'none';
    } else {
        tabAdmin.classList.add('active');
        tabUser.classList.remove('active');
        formAdmin.style.display = 'block';
        formUser.style.display = 'none';
    }
}

/**
 * 处理短信验证码发送
 */
async function handleSendSMS() {
    const phone = document.querySelector('#formAdmin input[name="phone"]');
    const btn = document.getElementById('smsBtn');

    if (!phone || !phone.value) {
        showToast('请先输入手机号', 'error');
        return;
    }

    if (!/^1[3-9]\d{9}$/.test(phone.value)) {
        showToast('请输入有效的手机号', 'error');
        return;
    }

    // 禁用按钮
    btn.disabled = true;
    btn.textContent = '发送中...';

    const result = await auth.sendSMSCode(phone.value);

    if (result.success) {
        showToast(`验证码: ${result.code}`, 'success');

        // 倒计时
        let countdown = 60;
        const timer = setInterval(() => {
            countdown--;
            btn.textContent = `${countdown}s后重发`;

            if (countdown <= 0) {
                clearInterval(timer);
                btn.disabled = false;
                btn.textContent = '📱 获取验证码';
            }
        }, 1000);
    } else {
        showToast(result.error, 'error');
        btn.disabled = false;
        btn.textContent = '📱 获取验证码';
    }
}

/**
 * 处理用户登录
 */
async function handleUserLogin(e) {
    e.preventDefault();

    const form = e.target;
    const username = form.querySelector('input[name="username"]').value.trim();
    const password = form.querySelector('input[name="password"]').value;

    if (!username || !password) {
        showToast('请输入用户名和密码', 'error');
        return;
    }

    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '登录中...';

    const result = await auth.login(username, password);

    if (result.success) {
        showToast('登录成功', 'success');
        setTimeout(() => {
            window.location.href = '/home';
        }, 500);
    } else {
        showToast(result.error, 'error');
        btn.disabled = false;
        btn.textContent = '登录';
    }
}

/**
 * 处理用户注册
 */
async function handleUserRegister(e) {
    e.preventDefault();

    const form = e.target;
    const username = form.querySelector('input[name="username"]').value.trim();
    const password = form.querySelector('input[name="password"]').value;
    const password2 = form.querySelector('input[name="password2"]').value;

    if (!username || !password || !password2) {
        showToast('请填写完整信息', 'error');
        return;
    }

    if (password !== password2) {
        showToast('两次密码不一致', 'error');
        return;
    }

    if (password.length < 4) {
        showToast('密码至少4个字符', 'error');
        return;
    }

    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '注册中...';

    const result = await auth.register(username, password, password2);

    if (result.success) {
        showToast('注册成功！请登录', 'success');
        setTimeout(() => {
            window.location.href = '/user/login';
        }, 1000);
    } else {
        showToast(result.error, 'error');
        btn.disabled = false;
        btn.textContent = '注册';
    }
}

/**
 * 处理管理员登录
 */
async function handleAdminLogin(e) {
    e.preventDefault();

    const form = e.target;
    const loginType = form.querySelector('input[name="login_type"]:checked').value;
    const username = form.querySelector('input[name="username"]').value.trim();

    let password = '';
    let smsCode = '';

    if (loginType === 'password') {
        password = form.querySelector('input[name="password"]').value;
        if (!username || !password) {
            showToast('请输入用户名和密码', 'error');
            return;
        }
    } else {
        smsCode = form.querySelector('input[name="sms_code"]').value.trim();
        if (!username || !smsCode) {
            showToast('请输入用户名和验证码', 'error');
            return;
        }
    }

    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '登录中...';

    const result = await auth.adminLogin(username, password, loginType, smsCode);

    if (result.success) {
        showToast('登录成功', 'success');
        if (result.redirect) {
            setTimeout(() => {
                window.location.href = result.redirect;
            }, 500);
        }
    } else {
        showToast(result.error, 'error');
        btn.disabled = false;
        btn.textContent = '登录';
    }
}

/**
 * 处理管理员注册
 */
async function handleAdminRegister(e) {
    e.preventDefault();

    const form = e.target;
    const username = form.querySelector('input[name="username"]').value.trim();
    const password = form.querySelector('input[name="password"]').value.trim();
    const phone = form.querySelector('input[name="phone"]').value.trim();
    const smsCode = form.querySelector('input[name="sms_code"]').value.trim();

    if (!username || !password || !phone || !smsCode) {
        showToast('请填写完整信息', 'error');
        return;
    }

    if (password.length < 6) {
        showToast('密码至少6个字符', 'error');
        return;
    }

    if (!/^1[3-9]\d{9}$/.test(phone)) {
        showToast('请输入有效的手机号', 'error');
        return;
    }

    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '注册中...';

    const result = await auth.adminRegister(username, password, phone, smsCode);

    if (result.success) {
        showToast('注册成功！请登录', 'success');
        setTimeout(() => {
            window.location.href = '/admin/login';
        }, 1000);
    } else {
        showToast(result.error, 'error');
        btn.disabled = false;
        btn.textContent = '注册';
    }
}

/**
 * 处理退出登录
 */
async function handleLogout() {
    if (confirm('确定要退出登录吗？')) {
        await auth.logout();
    }
}

// ========== 页面初始化 ==========

document.addEventListener('DOMContentLoaded', () => {
    // 绑定用户登录表单
    const userLoginForm = document.getElementById('userLoginForm');
    if (userLoginForm) {
        userLoginForm.addEventListener('submit', handleUserLogin);
    }

    // 绑定用户注册表单
    const userRegisterForm = document.getElementById('userRegisterForm');
    if (userRegisterForm) {
        userRegisterForm.addEventListener('submit', handleUserRegister);
    }

    // 绑定管理员登录表单
    const adminLoginForm = document.getElementById('adminLoginForm');
    if (adminLoginForm) {
        adminLoginForm.addEventListener('submit', handleAdminLogin);
    }

    // 绑定管理员注册表单
    const adminRegisterForm = document.getElementById('adminRegisterForm');
    if (adminRegisterForm) {
        adminRegisterForm.addEventListener('submit', handleAdminRegister);
    }

    // 绑定退出按钮
    const logoutBtns = document.querySelectorAll('.logout-btn');
    logoutBtns.forEach(btn => {
        btn.addEventListener('click', handleLogout);
    });

    // 绑定短信发送按钮
    const smsBtn = document.getElementById('smsBtn');
    if (smsBtn) {
        smsBtn.addEventListener('click', handleSendSMS);
    }
});

// ========== 导出全局函数 ==========

window.switchLoginType = switchLoginType;
window.switchRegisterRole = switchRegisterRole;
window.handleSendSMS = handleSendSMS;
window.handleLogout = handleLogout;