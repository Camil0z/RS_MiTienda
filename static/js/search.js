// search.js

document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('search-input');
    const productList = document.getElementById('product-list');
    const products = productList.getElementsByClassName('product-item');

    searchInput.addEventListener('input', function() {
        const filter = searchInput.value.toLowerCase();

        for (let i = 0; i < products.length; i++) {
            const product = products[i];
            const productName = product.getElementsByTagName('a')[0].innerText.toLowerCase();

            if (productName.includes(filter)) {
                product.style.display = "";
            } else {
                product.style.display = "none";
            }
        }
    });
});
