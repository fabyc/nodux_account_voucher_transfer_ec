#This file is part of the nodux_account_voucher_ec module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.

from trytond.pool import Pool
from .account_voucher import *

def register():
    Pool.register(
        AccountVoucher,
        module='nodux_account_voucher_transfer_ec', type_='model')
    Pool.register(
        VoucherReportTransfer,
        module='nodux_account_voucher_transfer_ec', type_='report')
