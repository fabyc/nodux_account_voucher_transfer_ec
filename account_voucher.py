# -*- coding: utf-8 -*-
#This file is part of the nodux_account_voucher_ec module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelSingleton, ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pyson import Eval, In
from trytond.pool import Pool
from trytond.report import Report
import pytz
from datetime import datetime,timedelta
import time

conversor = None
try:
    from numword import numword_es
    conversor = numword_es.NumWordES()
except:
    print("Warning: Does not possible import numword module!")
    print("Please install it...!")


__all__ = ['AccountVoucher', 'VoucherReportTransfer']

_STATES = {
    'readonly': In(Eval('state'), ['posted']),
}

class AccountVoucher(ModelSQL, ModelView):
    'Account Voucher'
    __name__ = 'account.voucher'

    valor_caja = fields.Numeric('Importe', states={
                'invisible': ~Eval('transfer', True),
                'readonly': In(Eval('state'), ['posted']),
                })

    cuenta_caja = fields.Many2One('account.account', 'Cuenta inicial', help='Cuenta de la que se realizara la transferencia',states={
                'invisible':  ~Eval('transfer', True),
                'readonly': In(Eval('state'), ['posted']),
                })

    cuenta_transfer = fields.Many2One('account.account', 'Cuenta a transferir el dinero', help = 'Cuenta a la que se realizara la transferencia',states={
                'invisible':  ~Eval('transfer', True),
                'readonly': In(Eval('state'), ['posted']),
                })


    @classmethod
    def __setup__(cls):
        super(AccountVoucher, cls).__setup__()

        cls._buttons.update({
                'transferir': {
                    'invisible': ~Eval('transfer', True),
                    'readonly': In(Eval('state'), ['posted']),
                    },
                })

        cls._buttons.update({
                'post': {
                    'invisible': Eval('transfer', True),
                    'readonly': In(Eval('state'), ['posted']),
                    },
                })

        del cls.party.states['required']
        cls.party.states['required'] = ~Eval('transfer', True)
        cls.party.states['invisible'] = Eval('transfer', True)
        cls.voucher_type.states['invisible'] = Eval('transfer', True)
        cls.pay_lines.states['invisible'] = Eval('transfer', True)
        cls.lines.states['invisible'] = Eval('transfer', True)
        cls.lines_credits.states['invisible'] =Eval('transfer', True)
        cls.lines_debits.states['invisible'] = Eval('transfer', True)
        cls.amount.states['invisible'] = Eval('transfer', True)
        cls.amount_to_pay.states['invisible'] = Eval('transfer', True)
        cls.amount_invoices.states['invisible'] = Eval('transfer', True)
        cls.move.states['invisible'] = Eval('transfer', True)
        cls.from_pay_invoice.states['invisible'] = Eval('transfer', True)
        cls.amount_to_pay_words.states['invisible'] = Eval('transfer', True)

    def prepare_lines_transfer(self):
        pool = Pool()
        Period = pool.get('account.period')
        Move = pool.get('account.move')

        move_lines = []
        line_move_ids = []
        move, = Move.create([{
            'period': Period.find(self.company.id, date=self.date),
            'journal': self.journal.id,
            'date': self.date,
            'origin': str(self),
        }])
        self.write([self], {
                'move': move.id,
                })

        if self.valor_caja:
            valor_new = self.valor_caja
        else:
            self.raise_user_error("No ha ingresado el valor a transferir")
        if self.cuenta_caja:
            cuenta_caja = self.cuenta_caja
        else:
            self.raise_user_error("No ha ingresado la cuenta de la que realizara la transferencia")
        if self.cuenta_transfer:
            cuenta_transfer = self.cuenta_transfer
        else:
            self.raise_user_error("No ha ingresado la cuenta a la que realizara la transferencia")


        move_lines.append({
            'description': self.number,
            'debit': Decimal(0.0),
            'credit': valor_new,
            'account': cuenta_caja.id,
            'move': move.id,
            'journal': self.journal.id,
            'period': Period.find(self.company.id, date=self.date),
            })
        print "La move lines", move_lines

        move_lines.append({
            'description': self.number,
            'debit': valor_new,
            'credit': Decimal(0.0),
            'account': cuenta_transfer.id,
            'move': move.id,
            'journal': self.journal.id,
            'period': Period.find(self.company.id, date=self.date),
            'date': self.date,
        })
        print "LAs lineas creada en create ", move_lines
        return move_lines

    def create_move_transfer(self, move_lines):
        print "Las lineas ", move_lines
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        Invoice = pool.get('account.invoice')
        created_lines = MoveLine.create(move_lines)
        print "Lineas creadas ", created_lines
        Move.post([self.move])
        return True

    def create_lines_reconcile(self):
        pool = Pool()
        Reconciled = pool.get('account.reconciliation')
        reconciled = Reconciled()

        reconciled.amount = self.valor_caja
        reconciled.conciliar = False
        reconciled.account = self.cuenta_transfer
        reconciled.state = 'draft'
        reconciled.date = self.date
        print "Guardar ", reconciled
        reconciled.save()

    @classmethod
    @ModelView.button
    def transferir(cls, vouchers):
        pool = Pool()
        for voucher in vouchers:
            voucher.set_number()
            voucher.create_lines_reconcile()
            move_lines = voucher.prepare_lines_transfer()
            voucher.create_move_transfer(move_lines)
        cls.write(vouchers, {'state': 'posted'})

class VoucherReportTransfer(Report):
    'Voucher Report Transfer'
    __name__ = 'account.voucher_transfer.report'

    @classmethod
    def parse(cls, report, objects, data, localcontext=None):
        Company = Pool().get('company.company')
        company_id = Transaction().context.get('company')
        company = Company(company_id)

        if company.timezone:
            timezone = pytz.timezone(company.timezone)
            dt = datetime.now()
            hora = datetime.astimezone(dt.replace(tzinfo=pytz.utc), timezone)

        localcontext['company'] = company
        localcontext['hora'] = hora.strftime('%H:%M:%S')
        localcontext['fecha'] = hora.strftime('%d/%m/%Y')
        localcontext['transfer'] = 'true'
        new_objs = []
        for obj in objects:
            if obj.valor_caja and conversor and not obj.amount_to_pay_words:
                obj.amount_to_pay_words = obj.get_amount2words(obj.valor_caja)
            new_objs.append(obj)

        return super(VoucherReportTransfer, cls).parse(report,
                new_objs, data, localcontext)
