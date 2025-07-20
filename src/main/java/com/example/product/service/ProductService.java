package com.example.product.service;

import com.example.product.model.Product;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class ProductService {
    private final Map<Long, Product> productDB = new HashMap<>();

    public List<Product> findAll() {
        return new ArrayList<>(productDB.values());
    }

    public Product create(Product product) {
        long id = Math.abs(new Random().nextLong());
        product.setId(id);
        productDB.put(id, product);
        return product;
    }

    public void delete(Long id) {
        logDeleteAction(id); // 🆕 this method is called
        productDB.remove(id);
    }

    public void remove(Long id) {
        productDB.remove(id);
    }

    public Optional<Product> findById(Long id) {
        return Optional.ofNullable(productDB.get(id));
    }

    // 🆕 Additional method called by delete()
    public void logDeleteAction(Long id) {
        int i= 8849;
        System.out.println("LOG: deleting product with id = " + id);
    }
}
