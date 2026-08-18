// AI 导诊系统 - 通用 JavaScript

// ========== 工具函数 ==========

/**
 * 显示 Toast 提示
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    // 添加样式
    Object.assign(toast.style, {
        position: 'fixed',
        top: '80px',
        right: '20px',
        padding: '12px 20px',
        background: type === 'error' ? '#fee2e2' : (type === 'success' ? '#dcfce7' : '#dbeafe'),
        color: type === 'error' ? '#dc2626' : (type === 'success' ? '#16a34a' : '#2563eb'),
        borderRadius: '8px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
        zIndex: '9999',
        animation: 'slideIn 0.3s ease',
        fontSize: '14px',
        maxWidth: '300px'
    });

    document.body.appendChild(toast);

    // 3秒后自动消失
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/**
 * 格式化日期时间
 */
function formatDateTime(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hour = String(date.getHours()).padStart(2, '0');
    const minute = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day} ${hour}:${minute}`;
}

/**
 * 截断文本
 */
function truncateText(text, maxLength = 100) {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

/**
 * 获取严重度标签颜色
 */
function getSeverityColor(severity) {
    const colors = {
        'red': '#ef4444',
        'yellow': '#f59e0b',
        'green': '#22c55e'
    };
    return colors[severity] || '#6b7280';
}

/**
 * 获取严重度标签文本
 */
function getSeverityLabel(severity) {
    const labels = {
        'red': '紧急',
        'yellow': '需尽快就医',
        'green': '可观察'
    };
    return labels[severity] || '未知';
}

/**
 * 确认对话框
 */
function confirmAction(message) {
    return confirm(message);
}

/**
 * 异步请求包装器
 */
async function fetchWithRetry(url, options = {}, retries = 3) {
    for (let i = 0; i < retries; i++) {
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response;
        } catch (error) {
            if (i === retries - 1) throw error;
            await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
        }
    }
}

// ========== 地区联动 ==========

/**
 * 加载城市列表
 */
async function loadCities(province) {
    if (!province) {
        const citySelect = document.getElementById('city');
        if (citySelect) {
            citySelect.innerHTML = '<option value="">请选择城市</option>';
        }
        const districtSelect = document.getElementById('district');
        if (districtSelect) {
            districtSelect.innerHTML = '<option value="">请选择区县</option>';
        }
        return;
    }

    try {
        const response = await fetch(`/api/cities?province=${encodeURIComponent(province)}`);
        const cities = await response.json();

        const citySelect = document.getElementById('city');
        if (citySelect) {
            citySelect.innerHTML = '<option value="">请选择城市</option>';
            cities.forEach(city => {
                const option = document.createElement('option');
                option.value = city;
                option.textContent = city;
                citySelect.appendChild(option);
            });
        }

        // 清空区县选择
        const districtSelect = document.getElementById('district');
        if (districtSelect) {
            districtSelect.innerHTML = '<option value="">请选择区县</option>';
        }
    } catch (error) {
        console.error('加载城市失败:', error);
        showToast('加载城市失败，请重试', 'error');
    }
}

/**
 * 加载区县列表
 */
async function loadDistricts(city) {
    if (!city) {
        const districtSelect = document.getElementById('district');
        if (districtSelect) {
            districtSelect.innerHTML = '<option value="">请选择区县</option>';
        }
        return;
    }

    try {
        const response = await fetch(`/api/districts?city=${encodeURIComponent(city)}`);
        const districts = await response.json();

        const districtSelect = document.getElementById('district');
        if (districtSelect) {
            districtSelect.innerHTML = '<option value="">请选择区县</option>';
            districts.forEach(district => {
                const option = document.createElement('option');
                option.value = district;
                option.textContent = district;
                districtSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('加载区县失败:', error);
        showToast('加载区县失败，请重试', 'error');
    }
}

/**
 * 初始化地区联动
 */
function initRegionSelectors() {
    const provinceSelect = document.getElementById('province');
    const citySelect = document.getElementById('city');
    const districtSelect = document.getElementById('district');

    if (provinceSelect) {
        provinceSelect.addEventListener('change', (e) => {
            loadCities(e.target.value);
        });
    }

    if (citySelect) {
        citySelect.addEventListener('change', (e) => {
            loadDistricts(e.target.value);
        });
    }
}

// ========== 表单验证 ==========

/**
 * 验证邮箱
 */
function validateEmail(email) {
    const pattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return pattern.test(email);
}

/**
 * 验证手机号
 */
function validatePhone(phone) {
    const pattern = /^1[3-9]\d{9}$/;
    return pattern.test(phone);
}

/**
 * 验证必填字段
 */
function validateRequired(form) {
    const requiredFields = form.querySelectorAll('[required]');
    const errors = [];

    requiredFields.forEach(field => {
        const value = field.value.trim();
        if (!value) {
            errors.push(field.name || field.id);
            field.classList.add('error');
        } else {
            field.classList.remove('error');
        }
    });

    return errors;
}

/**
 * 添加表单验证样式
 */
function addFormValidationStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .form-input.error {
            border-color: #ef4444 !important;
        }
        .error-message {
            color: #ef4444;
            font-size: 12px;
            margin-top: 4px;
        }
    `;
    document.head.appendChild(style);
}

// ========== 分页 ==========

/**
 * 创建分页控件
 */
function createPagination(currentPage, totalPages, onPageChange) {
    const container = document.createElement('div');
    container.className = 'pagination';

    container.innerHTML = `
        <button class="btn btn-sm ${currentPage <= 1 ? 'disabled' : ''}" ${currentPage <= 1 ? 'disabled' : ''}>上一页</button>
        <span class="pagination-info">${currentPage} / ${totalPages}</span>
        <button class="btn btn-sm ${currentPage >= totalPages ? 'disabled' : ''}" ${currentPage >= totalPages ? 'disabled' : ''}>下一页</button>
    `;

    const prevBtn = container.querySelector('button:first-child');
    const nextBtn = container.querySelector('button:last-child');

    if (prevBtn && currentPage > 1) {
        prevBtn.addEventListener('click', () => onPageChange(currentPage - 1));
    }

    if (nextBtn && currentPage < totalPages) {
        nextBtn.addEventListener('click', () => onPageChange(currentPage + 1));
    }

    return container;
}

// ========== 页面初始化 ==========

document.addEventListener('DOMContentLoaded', () => {
    // 初始化地区联动
    initRegionSelectors();

    // 添加表单验证样式
    addFormValidationStyles();

    // 为所有按钮添加点击动画
    document.querySelectorAll('.btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            if (!this.disabled) {
                this.style.transform = 'scale(0.98)';
                setTimeout(() => {
                    this.style.transform = '';
                }, 100);
            }
        });
    });
});

// 添加 CSS 动画
const animations = document.createElement('style');
animations.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }

    .pagination {
        display: flex;
        align-items: center;
        gap: 12px;
        justify-content: center;
        margin-top: 20px;
    }

    .pagination-info {
        font-size: 14px;
        color: #666;
    }
`;
document.head.appendChild(animations);