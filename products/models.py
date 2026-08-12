from django.db import models
from django.core.validators import MinValueValidator
from django.urls import reverse
from django.conf import settings
from django.core.exceptions import ValidationError


class Category(models.Model):
    """Simple product grouping, e.g. 'Beverages', 'Electronics', 'Stationery'."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    A sellable item. `price` here is the CURRENT/live selling price only.

    IMPORTANT: This price must NEVER be used to retroactively compute old
    invoices. Each InvoiceItem (in the invoices app) stores its own frozen
    `unit_price` field, copied from this product at the moment the invoice
    line was created. That means changing Product.price here only affects
    *future* invoices — existing invoices remain historically accurate.
    """

    class Unit(models.TextChoices):
        PIECE = 'PCS', 'Piece'
        KG = 'KG', 'Kilogram'
        LITRE = 'LTR', 'Litre'
        BOX = 'BOX', 'Box'
        PACK = 'PACK', 'Pack'
        METER = 'MTR', 'Meter'
        OTHER = 'OTHER', 'Other'

    name = models.CharField(max_length=200)
    sku = models.CharField(
        max_length=50, unique=True,
        help_text="Stock Keeping Unit / product code. Auto-generated if left blank."
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='products'
    )
    description = models.TextField(blank=True)

    # --- Pricing ---
    price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Current selling price. Changing this does not affect past invoices."
    )
    cost_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
        help_text="What the business pays to acquire/produce this item. Used for profit reports."
    )

    # --- Stock ---
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.PIECE)
    stock_quantity = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
        help_text="Current quantity on hand. Adjusted automatically via StockMovement records."
    )
    reorder_level = models.DecimalField(
        max_digits=12, decimal_places=2, default=5,
        validators=[MinValueValidator(0)],
        help_text="Trigger a 'low stock' warning when stock_quantity falls to/below this level."
    )
    track_stock = models.BooleanField(
        default=True,
        help_text="Disable for services or items where stock isn't tracked (e.g. labor, delivery fees)."
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Inactive products are hidden from sale but preserved for historical invoices."
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='products_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['sku']),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def get_absolute_url(self):
        return reverse('products:product_detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = self._generate_sku()
        super().save(*args, **kwargs)

    def _generate_sku(self):
        """Auto-generates a simple sequential SKU like PRD-00001 if none provided."""
        last = Product.objects.order_by('-id').first()
        next_id = (last.id + 1) if last else 1
        return f"PRD-{next_id:05d}"

    @property
    def is_low_stock(self):
        if not self.track_stock:
            return False
        return self.stock_quantity <= self.reorder_level

    @property
    def is_out_of_stock(self):
        if not self.track_stock:
            return False
        return self.stock_quantity <= 0

    @property
    def profit_margin(self):
        if self.cost_price and self.cost_price > 0:
            return round(((self.price - self.cost_price) / self.cost_price) * 100, 2)
        return None

    def has_sufficient_stock(self, quantity):
        """Used by invoices app to validate a line item before saving."""
        if not self.track_stock:
            return True
        return self.stock_quantity >= quantity

    def adjust_stock(self, quantity, movement_type, reference='', user=None, notes=''):
        """
        Central, safe method for changing stock. ALWAYS use this instead of
        editing stock_quantity directly, so every change is logged in
        StockMovement and can be audited/reported on later.

        quantity: positive number. Direction is determined by movement_type.
        movement_type: one of StockMovement.MovementType choices.
        """
        if not self.track_stock:
            return

        quantity = abs(quantity)
        inbound_types = {
            StockMovement.MovementType.PURCHASE,
            StockMovement.MovementType.RETURN,
            StockMovement.MovementType.ADJUSTMENT_IN,
        }
        outbound_types = {
            StockMovement.MovementType.SALE,
            StockMovement.MovementType.ADJUSTMENT_OUT,
            StockMovement.MovementType.DAMAGED,
        }

        if movement_type in outbound_types and self.stock_quantity < quantity:
            raise ValidationError(
                f"Insufficient stock for '{self.name}'. "
                f"Available: {self.stock_quantity}, requested: {quantity}."
            )

        if movement_type in inbound_types:
            self.stock_quantity += quantity
        elif movement_type in outbound_types:
            self.stock_quantity -= quantity
        else:
            raise ValidationError(f"Unknown movement type: {movement_type}")

        self.save(update_fields=['stock_quantity', 'updated_at'])

        StockMovement.objects.create(
            product=self,
            movement_type=movement_type,
            quantity=quantity,
            resulting_stock=self.stock_quantity,
            reference=reference,
            notes=notes,
            created_by=user,
        )


class StockMovement(models.Model):
    """
    Immutable audit log of every stock change. Never edited or deleted —
    this is the historical record for 'why is stock at X?' questions and
    for stock reports.
    """

    class MovementType(models.TextChoices):
        PURCHASE = 'PURCHASE', 'Stock Purchase / Restock'
        SALE = 'SALE', 'Sale (Invoice)'
        RETURN = 'RETURN', 'Customer Return'
        ADJUSTMENT_IN = 'ADJUSTMENT_IN', 'Manual Adjustment (Increase)'
        ADJUSTMENT_OUT = 'ADJUSTMENT_OUT', 'Manual Adjustment (Decrease)'
        DAMAGED = 'DAMAGED', 'Damaged / Written Off'

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    resulting_stock = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Snapshot of stock_quantity immediately after this movement."
    )
    reference = models.CharField(
        max_length=100, blank=True,
        help_text="e.g. Invoice number, purchase order number."
    )
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', '-created_at']),
        ]

    def __str__(self):
        return f"{self.product.name}: {self.get_movement_type_display()} ({self.quantity})"



